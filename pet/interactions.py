"""Interactions: things the owner (you) can do to the pet from the input area.

They take effect immediately, don't use up a tick, and are stored in the pet's memory.

To add one, write a function and decorate it with @interaction(...):

    @interaction("brush", key="b", label="Brush")
    def brush(state: PetState) -> None:
        state.apply({"cleanliness": +15, "mood": +5})
"""
from dataclasses import dataclass
from typing import Callable

from .state import PetState

InteractionFn = Callable[[PetState], None]


@dataclass(frozen=True)
class Interaction:
    name: str           # stored in the pet's memory as "owner_<name>"
    key: str            # what the owner types
    label: str          # display name
    fn: InteractionFn   # function that changes the stats


INTERACTIONS: dict[str, Interaction] = {}  # by key


def interaction(name: str, *, key: str, label: str) -> Callable[[InteractionFn], InteractionFn]:
    """Register an owner interaction."""
    def register(fn: InteractionFn) -> InteractionFn:
        if key in INTERACTIONS:
            raise ValueError(f"interaction key {key!r} is registered twice")
        INTERACTIONS[key] = Interaction(name, key, label, fn)
        return fn
    return register


# ---------------------------------------------------------------- interactions

@interaction("feed", key="f", label="Feed")
def feed(state: PetState) -> None:
    state.apply({"fullness": +30})


@interaction("cuddle", key="c", label="Cuddle")
def cuddle(state: PetState) -> None:
    state.apply({"social": +30, "mood": +10})


# ---------------------------------------------------------------- apply

def apply_interaction(state: PetState, item: Interaction) -> dict[str, int]:
    """Run the interaction and return the actual stat changes."""
    before = state.to_dict()
    item.fn(state)
    after = state.to_dict()
    return {k: after[k] - before[k] for k in after if after[k] != before[k]}
