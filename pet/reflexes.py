"""Reflexes: when a stat gets too low, the pet does a set action without asking the LLM.

How the next action is picked (engine.py), in this order:
    1. the action that just finished picks it (its `then`, actions.py)
    2. a reflex: the first one below whose stat is under its threshold picks it
    3. the LLM picks it from the pet's thought and memory

To add one, add a line to REFLEXES; the order is the priority.
A reflex may pick any action, including ones the LLM can't pick (llm=False).
"""
from dataclasses import dataclass

from .actions import ACTIONS, Action
from .state import PetState


@dataclass(frozen=True)
class Reflex:
    stat: str      # a PetState field
    below: float   # fires while the stat is under this
    action: str    # the action it picks


REFLEXES: list[Reflex] = [
    Reflex("health", below=20, action="rest"),
    Reflex("fullness", below=20, action="scavenge"),
    Reflex("energy", below=15, action="sleep"),
]

# Catch typos when the module loads, not when the reflex first fires
for _r in REFLEXES:
    if _r.stat not in PetState.names():
        raise ValueError(f"reflex: {_r.stat!r} is not a stat; choose from {PetState.names()}")
    if _r.action not in ACTIONS:
        raise ValueError(f"reflex on {_r.stat}: {_r.action!r} is not an action")


def reflex_action(state: PetState) -> tuple[Action, Reflex] | None:
    """The action of the first reflex that fires now, with the reflex; None if none does."""
    for r in REFLEXES:
        if getattr(state, r.stat) < r.below:
            return ACTIONS[r.action], r
    return None
