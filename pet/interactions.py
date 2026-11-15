"""Interactions: things the owner (you) can do to the pet from the input area.

They take effect immediately, don't use up a tick, and are stored in the pet's memory.

To add one, write a function and decorate it with @interaction(...):

    @interaction("treat", key="t", label="Treat")
    def treat(state: PetState, world: World) -> None:
        state.apply({"fullness": +10, "social": +5})
"""
from dataclasses import dataclass
from typing import Callable

from .state import PetState
from .world import BOWL_MAX, World

InteractionFn = Callable[[PetState, World], None]


@dataclass(frozen=True)
class Interaction:
    name: str           # stored in the pet's memory as "owner_<name>"
    key: str            # what the owner types
    label: str          # display name
    fn: InteractionFn   # function that changes the stats or the world


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
def feed(state: PetState, world: World) -> None:
    # Puts a portion in the bowl; the pet has to choose to eat it. A full bowl takes no more.
    world.bowl = min(world.bowl + 1, BOWL_MAX)


@interaction("cuddle", key="c", label="Cuddle")
def cuddle(state: PetState, world: World) -> None:
    state.apply({"social": +30})


# ---------------------------------------------------------------- apply

def apply_interaction(state: PetState, world: World, item: Interaction) -> dict[str, int]:
    """Run the interaction and return the actual changes (stats and world)."""
    before = {**state.to_dict(), **world.to_dict()}
    item.fn(state, world)
    after = {**state.to_dict(), **world.to_dict()}
    return {k: after[k] - before[k] for k in after if after[k] != before[k]}
