"""Actions: once the LLM picks an action, the functions here change the stats.

To add an action, write a function and decorate it with @action(...).
The LLM prompt, the supervisor and the fallback rule all pick it up
automatically; no other file needs to change.

    @action("walk", "Walk", "go out for a walk", restores="mood",
            animation="walk", text="🐕 Happily heads out for a walk!")
    def walk(state: PetState) -> None:
        state.apply({"mood": +20, "energy": -10})

The function receives the current state and can contain any logic
(conditions, randomness, ...). Use state.apply({...}) to change stats;
values are clamped to 0-100 automatically.
"""
from dataclasses import dataclass
from typing import Callable

from .state import PetState

ActionFn = Callable[[PetState], None]


@dataclass(frozen=True)
class Action:
    name: str
    label: str              # display name
    description: str        # shown to the LLM
    restores: str | None    # main stat this action restores (used by the supervisor and fallback rule)
    animation: str          # animation key for the future graphical display
    text: str               # current text representation
    fn: ActionFn            # function that changes the stats

    def preview(self) -> dict[str, int]:
        """Run the action once on a mid-range state to show its effect (for the LLM)."""
        s = PetState(**{k: 50 for k in PetState.names()})
        before = s.to_dict()
        self.fn(s)
        return {k: v - before[k] for k, v in s.to_dict().items() if v != before[k]}


ACTIONS: dict[str, Action] = {}


def action(name: str, label: str, description: str, *, restores: str | None,
           animation: str, text: str) -> Callable[[ActionFn], ActionFn]:
    """Register an action function."""
    def register(fn: ActionFn) -> ActionFn:
        if name in ACTIONS:
            raise ValueError(f"action {name} is registered twice")
        if restores is not None and restores not in PetState.names():
            raise ValueError(f"action {name}: restores={restores} is not a valid stat")
        ACTIONS[name] = Action(name, label, description, restores, animation, text, fn)
        return fn
    return register


# ---------------------------------------------------------------- action functions

@action("eat", "Eat", "eat some food to restore fullness", restores="fullness",
        animation="eat", text="🍖 Gobbles down its food...")
def eat(state: PetState) -> None:
    state.apply({"fullness": +35, "energy": +5, "cleanliness": -5})


@action("sleep", "Sleep", "take a nap to restore a lot of energy", restores="energy",
        animation="sleep", text="💤 Curls up into a ball and snores away...")
def sleep(state: PetState) -> None:
    state.apply({"energy": +45, "fullness": -10, "social": -5})


@action("play", "Play", "play with toys; lifts mood but uses energy", restores="mood",
        animation="play", text="🎾 Chases the ball all over the place!")
def play(state: PetState) -> None:
    state.apply({"mood": +25, "energy": -15, "fullness": -10, "cleanliness": -10})


@action("bathe", "Bathe", "take a bath to greatly improve cleanliness", restores="cleanliness",
        animation="bathe", text="🛁 Splashes water around the tub...")
def bathe(state: PetState) -> None:
    state.apply({"cleanliness": +45, "mood": -5, "health": +5})


@action("seek_attention", "Cuddle", "ask the owner for attention to meet social needs",
        restores="social", animation="cuddle", text="🥺 Rubs against the owner's leg, wants pets~")
def seek_attention(state: PetState) -> None:
    state.apply({"social": +35, "mood": +10, "energy": -5})


@action("rest", "Rest", "lie down quietly to slowly recover health and energy", restores="health",
        animation="rest", text="🛋️ Lies quietly in its bed, resting.")
def rest(state: PetState) -> None:
    state.apply({"health": +15, "energy": +15, "mood": -5})


@action("idle", "Idle", "do nothing", restores=None,
        animation="idle", text="😶 Stares blankly out the window...")
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


def apply_action(state: PetState, action_name: str) -> dict[str, int]:
    """Run the action function, then every per-tick rule in order; return the actual change."""
    from .rules import RULES  # avoid a circular import

    before = state.to_dict()
    ACTIONS[action_name].fn(state)
    for rule in RULES:
        rule(state)
    after = state.to_dict()
    return {k: after[k] - before[k] for k in after if after[k] != before[k]}
