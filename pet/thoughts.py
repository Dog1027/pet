"""Thoughts: the one thing on the pet's mind right now, worked out by the program from its stats.

Flow:  stats -> (code) one thought -> (LLM) action -> (code) stats change

The LLM never sees the stats. It only sees the single most urgent thought and picks an action.

Each thought is a function that returns how urgent it is (0 = not felt, higher = more urgent).
The program picks the most urgent one; if none is felt, the pet is DEFAULT_THOUGHT.
To add a thought, write such a function and decorate it with @thought("name"):

    @thought("scared")
    def scared(state: PetState) -> int:
        return 100 if state.health < 10 else 0
"""
from typing import Callable

from .state import PetState

ThoughtFn = Callable[[PetState], int]

THOUGHTS: dict[str, ThoughtFn] = {}  # on a tie, the one registered first wins
DEFAULT_THOUGHT = "content"          # when no thought is felt


def thought(name: str) -> Callable[[ThoughtFn], ThoughtFn]:
    """Register a thought."""
    def register(fn: ThoughtFn) -> ThoughtFn:
        if name in THOUGHTS:
            raise ValueError(f"thought {name} is registered twice")
        THOUGHTS[name] = fn
        return fn
    return register


FELT_BELOW = 60  # a need is only felt once its stat drops below this


def need(value: int) -> int:
    """Urgency of a need, from a 0-100 stat where higher is better: the lower the stat,
    the more urgent; 0 while the stat is still FELT_BELOW or above."""
    return 100 - value if value < FELT_BELOW else 0


# ---------------------------------------------------------------- thoughts

@thought("hungry")
def hungry(state: PetState) -> int:
    return need(state.fullness)


@thought("tired")
def tired(state: PetState) -> int:
    return need(state.energy)


@thought("bored")
def bored(state: PetState) -> int:
    return need(state.mood)


@thought("dirty")
def dirty(state: PetState) -> int:
    return need(state.cleanliness)


@thought("sick")
def sick(state: PetState) -> int:
    return need(state.health)


@thought("lonely")
def lonely(state: PetState) -> int:
    return need(state.social)


# ---------------------------------------------------------------- current thought

def current_thought(state: PetState) -> str:
    """The single most urgent thought right now, or DEFAULT_THOUGHT if nothing is felt."""
    best, best_urgency = DEFAULT_THOUGHT, 0
    for name, fn in THOUGHTS.items():
        urgency = fn(state)
        if urgency > best_urgency:
            best, best_urgency = name, urgency
    return best
