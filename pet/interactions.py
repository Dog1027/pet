"""Interactions: things the owner (you) can do to the pet.

They take effect immediately, whatever the pet is doing, and are stored in the pet's memory.

To add one, write a function and decorate it with @interaction(...). It receives the pet's state
and the world, plus any options the display sent (as keyword arguments), and makes its changes
at once:

    @interaction("treat", key="t", label="Treat")
    def treat(state: PetState, world: World) -> None:
        state.apply({"fullness": +10, "social": +5})

action (optional): an action (actions.py) the pet starts doing right away. It interrupts
whatever the pet was doing; that action ends there and its `then` doesn't run. Use it for
interactions that take time: the action's duration is how long the interaction lasts.
"""
from dataclasses import dataclass
from typing import Callable

from .state import PetState
from .world import World, diff, inside

InteractionFn = Callable[..., None]  # (state, world, **options)

FOOD_PORTION = 30.0  # food put down by one Feed (points of fullness)


@dataclass(frozen=True)
class Interaction:
    name: str           # stored in the pet's memory as "owner_<name>"
    key: str            # what the owner types
    label: str          # display name
    fn: InteractionFn   # function that changes the stats or the world at once
    action: str | None = None  # action the pet starts doing, interrupting the current one


INTERACTIONS: dict[str, Interaction] = {}  # by key


def interaction(name: str, *, key: str, label: str,
                action: str | None = None) -> Callable[[InteractionFn], InteractionFn]:
    """Register an owner interaction."""
    def register(fn: InteractionFn) -> InteractionFn:
        if key in INTERACTIONS:
            raise ValueError(f"interaction key {key!r} is registered twice")
        INTERACTIONS[key] = Interaction(name, key, label, fn, action)
        return fn
    return register


# ---------------------------------------------------------------- interactions

@interaction("feed", key="f", label="Feed")
def feed(state: PetState, world: World, x: int | None = None, y: int | None = None) -> None:
    """Puts a portion of food at (x, y); without a position, where the pet is.
    The pet has to be there and choose to eat it."""
    if x is None or y is None:
        x, y = world.x, world.y
    if not isinstance(x, int) or not isinstance(y, int) or not inside(x, y):
        raise ValueError(f"can't put food at ({x}, {y})")
    world.put("food", x, y, FOOD_PORTION)


@interaction("cuddle", key="c", label="Cuddle", action="cuddled")
def cuddle(state: PetState, world: World) -> None:
    pass  # nothing at once: the "cuddled" action raises social over its duration


# ---------------------------------------------------------------- apply

def apply_interaction(state: PetState, world: World, item: Interaction, **options) -> dict[str, float]:
    """Run the interaction and return the actual changes (stats and world).
    Raises TypeError / ValueError for options it doesn't accept."""
    before = {**state.to_dict(), **world.numbers()}
    item.fn(state, world, **options)
    return diff(before, {**state.to_dict(), **world.numbers()})
