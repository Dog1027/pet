"""Actions: the functions here change the stats.

The LLM never sees actions. It picks a thought, and the thought's decision tree
(thoughts.py) picks which action to run.

To add an action, write a function and decorate it with @action(...),
then return its name from a decision tree in thoughts.py.

    def can_walk(state: PetState) -> bool:
        return state.energy >= 20          # too tired to go out

    @action("walk", "Walk", animation="walk", condition=can_walk)
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
    animation: str          # animation key for the future graphical display
    fn: ActionFn            # function that changes the stats
    condition: ConditionFn  # whether the action can change the stats right now


@dataclass(frozen=True)
class ActionResult:
    delta: dict[str, int]   # actual change this tick (action + per-tick rules)
    applied: bool           # False if the condition blocked the action's effect


ACTIONS: dict[str, Action] = {}


def action(name: str, label: str, *, animation: str,
           condition: ConditionFn = always) -> Callable[[ActionFn], ActionFn]:
    """Register an action function."""
    def register(fn: ActionFn) -> ActionFn:
        if name in ACTIONS:
            raise ValueError(f"action {name} is registered twice")
        ACTIONS[name] = Action(name, label, animation, fn, condition)
        return fn
    return register


# ---------------------------------------------------------------- action functions
# Each action has a can_<name> condition. They all return True for now;
# fill them in to decide when the action is able to change the stats.

def can_eat(state: PetState) -> bool:
    return True


@action("eat", "Eat", animation="eat", condition=can_eat)
def eat(state: PetState) -> None:
    state.apply({"fullness": +35, "energy": +5, "cleanliness": -5})


def can_sleep(state: PetState) -> bool:
    return True


@action("sleep", "Sleep", animation="sleep", condition=can_sleep)
def sleep(state: PetState) -> None:
    state.apply({"energy": +45, "fullness": -10, "social": -5})


def can_play(state: PetState) -> bool:
    return True


@action("play", "Play", animation="play", condition=can_play)
def play(state: PetState) -> None:
    state.apply({"mood": +25, "energy": -15, "fullness": -10, "cleanliness": -10})


def can_bathe(state: PetState) -> bool:
    return True


@action("bathe", "Bathe", animation="bathe", condition=can_bathe)
def bathe(state: PetState) -> None:
    state.apply({"cleanliness": +45, "mood": -5, "health": +5})


def can_seek_attention(state: PetState) -> bool:
    return True


@action("seek_attention", "Cuddle", animation="cuddle", condition=can_seek_attention)
def seek_attention(state: PetState) -> None:
    state.apply({"social": +35, "mood": +10, "energy": -5})


def can_rest(state: PetState) -> bool:
    return True


@action("rest", "Rest", animation="rest", condition=can_rest)
def rest(state: PetState) -> None:
    state.apply({"health": +15, "energy": +15, "mood": -5})


@action("idle", "Idle", animation="idle")
def idle(state: PetState) -> None:
    pass


# ---------------------------------------------------------------- apply

def apply_action(state: PetState, action_name: str | None) -> ActionResult:
    """Check the condition, run the action function if allowed, then every per-tick rule in order.
    action_name=None means no action this tick (e.g. the LLM gave no usable reply): only the rules run."""
    from .rules import RULES  # avoid a circular import

    before = state.to_dict()
    applied = False
    if action_name is not None:
        act = ACTIONS[action_name]
        applied = act.condition(state)
        if applied:
            act.fn(state)
    for rule in RULES:  # time passes either way
        rule(state)
    after = state.to_dict()
    delta = {k: after[k] - before[k] for k in after if after[k] != before[k]}
    return ActionResult(delta, applied)
