"""Thoughts: what the pet is feeling right now, worked out by the program from its stats.

Flow:  stats -> (code) thoughts -> (LLM) action -> (code) stats change

The LLM never sees the numbers. It sees the current thoughts, each with a strength
(low / medium / high), and picks an action.

To add a thought, write a function that returns its strength (or None when the pet
doesn't feel it) and decorate it with @thought("name"):

    @thought("scared")
    def scared(state: PetState) -> str | None:
        return "high" if state.health < 10 else None
"""
from typing import Callable

from .state import PetState

ThoughtFn = Callable[[PetState], str | None]

THOUGHTS: dict[str, ThoughtFn] = {}  # in the order they are listed to the LLM


def thought(name: str) -> Callable[[ThoughtFn], ThoughtFn]:
    """Register a thought."""
    def register(fn: ThoughtFn) -> ThoughtFn:
        if name in THOUGHTS:
            raise ValueError(f"thought {name} is registered twice")
        THOUGHTS[name] = fn
        return fn
    return register


def strength(value: int) -> str | None:
    """How strongly a need is felt, from a 0-100 stat where higher is better."""
    if value < 20:
        return "high"
    if value < 40:
        return "medium"
    if value < 60:
        return "low"
    return None


# ---------------------------------------------------------------- thoughts

@thought("hungry")
def hungry(state: PetState) -> str | None:
    return strength(state.fullness)


@thought("tired")
def tired(state: PetState) -> str | None:
    return strength(state.energy)


@thought("bored")
def bored(state: PetState) -> str | None:
    return strength(state.mood)


@thought("dirty")
def dirty(state: PetState) -> str | None:
    return strength(state.cleanliness)


@thought("sick")
def sick(state: PetState) -> str | None:
    return strength(state.health)


@thought("lonely")
def lonely(state: PetState) -> str | None:
    return strength(state.social)


# ---------------------------------------------------------------- current thoughts / changes

def current_thoughts(state: PetState) -> dict[str, str]:
    """The thoughts the pet has right now: {name: strength}. Thoughts it doesn't have are left out."""
    out = {}
    for name, fn in THOUGHTS.items():
        level = fn(state)
        if level:
            out[name] = level
    return out


def describe_change(before: dict[str, str], after: dict[str, str]) -> str:
    """How the thoughts changed over a tick, e.g. "hungry high>none,dirty none>low".
    This is the result text stored in the pet's memory."""
    changes = [
        f"{name} {before.get(name, 'none')}>{after.get(name, 'none')}"
        for name in THOUGHTS
        if before.get(name) != after.get(name)
    ]
    return ",".join(changes) if changes else "no change"
