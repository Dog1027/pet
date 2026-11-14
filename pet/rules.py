"""Per-tick rules: whatever action was chosen, these functions run after it, in the order written.

To add a rule, write a function and decorate it with @rule.

    @rule
    def lonely_hurts_health(state: PetState) -> None:
        if state.social < 10:
            state.apply({"health": -2})
"""
from typing import Callable

from .state import PetState

RuleFn = Callable[[PetState], None]
RULES: list[RuleFn] = []


def rule(fn: RuleFn) -> RuleFn:
    """Register a per-tick rule."""
    RULES.append(fn)
    return fn


# ---------------------------------------------------------------- passage of time

@rule
def hunger_over_time(state: PetState) -> None:
    """The pet slowly gets hungry."""
    state.apply({"fullness": -6})


@rule
def tired_over_time(state: PetState) -> None:
    """Energy slowly drops."""
    state.apply({"energy": -4})


@rule
def lonely_over_time(state: PetState) -> None:
    """The pet gets lonelier."""
    state.apply({"social": -4})


# ---------------------------------------------------------------- stats affecting each other

@rule
def starving_hurts_health(state: PetState) -> None:
    """Being too hungry hurts health."""
    if state.fullness < 20:
        state.apply({"health": -8})
