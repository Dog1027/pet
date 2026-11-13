"""Actions: once the LLM picks an action, the functions here change the stats.

To add an action, write a function and decorate it with @action(...).
The LLM prompt, the supervisor and the fallback rule all pick it up
automatically; no other file needs to change.

    def can_walk(state: PetState) -> bool:
        return state.energy >= 20          # too tired to go out

    @action("walk", "Walk", "go out for a walk", restores="mood",
            animation="walk", condition=can_walk)
    def walk(state: PetState) -> None:
        state.apply({"mood": +20, "energy": -10})

The action function receives the current state and can contain any logic
(conditions, randomness, ...). Use state.apply({...}) to change stats;
values are clamped to 0-100 automatically.

condition (optional) is called first, with the state before the action.
If it returns False the action has no effect this tick (the pet still spends
the tick on it, and the per-tick rules still run). Leave it out to always apply.
"""
from dataclasses import dataclass
from typing import Callable

from .state import PetState

ActionFn = Callable[[PetState], None]
ConditionFn = Callable[[PetState], bool]


def always(state: PetState) -> bool:
    """Default condition: the action always takes effect."""
    return True


@dataclass(frozen=True)
class Action:
    name: str
    label: str              # display name
    description: str        # shown to the LLM
    restores: str | None    # main stat this action restores (used by the supervisor and fallback rule)
    animation: str          # animation key for the future graphical display
    fn: ActionFn            # function that changes the stats
    condition: ConditionFn  # whether the action can change the stats right now

    def preview(self) -> dict[str, int]:
        """Run the action once on a mid-range state to show its effect (for the LLM).
        Ignores the condition: it shows what the action does when it works."""
        s = PetState(**{k: 50 for k in PetState.names()})
        before = s.to_dict()
        self.fn(s)
        return {k: v - before[k] for k, v in s.to_dict().items() if v != before[k]}


@dataclass(frozen=True)
class ActionResult:
    delta: dict[str, int]   # actual change this tick (action + per-tick rules)
    applied: bool           # False if the condition blocked the action's effect


ACTIONS: dict[str, Action] = {}


def action(name: str, label: str, description: str, *, restores: str | None,
           animation: str, condition: ConditionFn = always) -> Callable[[ActionFn], ActionFn]:
    """Register an action function."""
    def register(fn: ActionFn) -> ActionFn:
        if name in ACTIONS:
            raise ValueError(f"action {name} is registered twice")
        if restores is not None and restores not in PetState.names():
            raise ValueError(f"action {name}: restores={restores} is not a valid stat")
        ACTIONS[name] = Action(name, label, description, restores, animation, fn, condition)
        return fn
    return register


# ---------------------------------------------------------------- action functions
# Each action has a can_<name> condition. They all return True for now;
# fill them in to decide when the action is able to change the stats.

def can_eat(state: PetState) -> bool:
    return True


@action("eat", "Eat", "eat some food to restore fullness", restores="fullness",
        animation="eat", condition=can_eat)
def eat(state: PetState) -> None:
    state.apply({"fullness": +35, "energy": +5, "cleanliness": -5})


def can_sleep(state: PetState) -> bool:
    return True


@action("sleep", "Sleep", "take a nap to restore a lot of energy", restores="energy",
        animation="sleep", condition=can_sleep)
def sleep(state: PetState) -> None:
    state.apply({"energy": +45, "fullness": -10, "social": -5})


def can_play(state: PetState) -> bool:
    return True


@action("play", "Play", "play with toys; lifts mood but uses energy", restores="mood",
        animation="play", condition=can_play)
def play(state: PetState) -> None:
    state.apply({"mood": +25, "energy": -15, "fullness": -10, "cleanliness": -10})


def can_bathe(state: PetState) -> bool:
    return True


@action("bathe", "Bathe", "take a bath to greatly improve cleanliness", restores="cleanliness",
        animation="bathe", condition=can_bathe)
def bathe(state: PetState) -> None:
    state.apply({"cleanliness": +45, "mood": -5, "health": +5})


def can_seek_attention(state: PetState) -> bool:
    return True


@action("seek_attention", "Cuddle", "ask the owner for attention to meet social needs",
        restores="social", animation="cuddle", condition=can_seek_attention)
def seek_attention(state: PetState) -> None:
    state.apply({"social": +35, "mood": +10, "energy": -5})


def can_rest(state: PetState) -> bool:
    return True


@action("rest", "Rest", "lie down quietly to slowly recover health and energy", restores="health",
        animation="rest", condition=can_rest)
def rest(state: PetState) -> None:
    state.apply({"health": +15, "energy": +15, "mood": -5})


@action("idle", "Idle", "do nothing", restores=None,
        animation="idle")
def idle(state: PetState) -> None:
    pass


# ---------------------------------------------------------------- lookup / apply

def action_for_stat(stat: str) -> str | None:
    """Find the action that restores a stat (first registered wins)."""
    return next((a.name for a in ACTIONS.values() if a.restores == stat), None)


def safe_action(state: PetState) -> str:
    """Rule-based safe choice: restore the lowest stat that some action can restore."""
    for stat, _ in sorted(state.to_dict().items(), key=lambda kv: kv[1]):
        if name := action_for_stat(stat):
            return name
    return next(iter(ACTIONS))


def apply_action(state: PetState, action_name: str) -> ActionResult:
    """Check the condition, run the action function if allowed, then every per-tick rule in order."""
    from .rules import RULES  # avoid a circular import

    act = ACTIONS[action_name]
    before = state.to_dict()
    applied = act.condition(state)
    if applied:
        act.fn(state)
    for rule in RULES:  # time passes either way
        rule(state)
    after = state.to_dict()
    delta = {k: after[k] - before[k] for k in after if after[k] != before[k]}
    return ActionResult(delta, applied)
