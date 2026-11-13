"""Thoughts: what the LLM chooses from, and the decision trees that turn a thought into an action.

Flow:  stats -> (LLM) thought -> (decision tree, code) action -> (code) stats change

The LLM only ever sees the list of thought names. Each thought has a decision function
that receives the current state and returns the name of the action to perform.
For now every tree maps straight to one action; extend them with conditions later:

    @thought("eat", stat="fullness")
    def decide_eat(state: PetState) -> str:
        if not has_food():            # your own condition
            return "ask_for_food"     # any action registered in actions.py
        return "eat"

To add a thought, write a decision function and decorate it with @thought(...).
The LLM prompt, the supervisor and the fallback all pick it up automatically.
"""
from dataclasses import dataclass
from typing import Callable

from .actions import ACTIONS
from .state import PetState

DecideFn = Callable[[PetState], str]


@dataclass(frozen=True)
class Thought:
    name: str            # what the LLM outputs
    stat: str | None     # the stat this thought is about (used by the supervisor and the fallback)
    decide: DecideFn     # decision tree: state -> action name


THOUGHTS: dict[str, Thought] = {}


def thought(name: str, *, stat: str | None) -> Callable[[DecideFn], DecideFn]:
    """Register a thought and its decision tree."""
    def register(fn: DecideFn) -> DecideFn:
        if name in THOUGHTS:
            raise ValueError(f"thought {name} is registered twice")
        if stat is not None and stat not in PetState.names():
            raise ValueError(f"thought {name}: stat={stat} is not a valid stat")
        THOUGHTS[name] = Thought(name, stat, fn)
        return fn
    return register


# ---------------------------------------------------------------- decision trees

@thought("eat", stat="fullness")
def decide_eat(state: PetState) -> str:
    return "eat"


@thought("sleep", stat="energy")
def decide_sleep(state: PetState) -> str:
    return "sleep"


@thought("play", stat="mood")
def decide_play(state: PetState) -> str:
    return "play"


@thought("bathe", stat="cleanliness")
def decide_bathe(state: PetState) -> str:
    return "bathe"


@thought("cuddle", stat="social")
def decide_cuddle(state: PetState) -> str:
    return "seek_attention"


@thought("rest", stat="health")
def decide_rest(state: PetState) -> str:
    return "rest"


@thought("nothing", stat=None)
def decide_nothing(state: PetState) -> str:
    return "idle"


# ---------------------------------------------------------------- lookup / resolve

def resolve(thought_name: str, state: PetState) -> str:
    """Run the thought's decision tree and return the action name it picked."""
    action_name = THOUGHTS[thought_name].decide(state)
    if action_name not in ACTIONS:
        raise ValueError(f"thought {thought_name} resolved to unknown action {action_name!r}")
    return action_name


def safe_thought(state: PetState) -> str:
    """Rule-based safe choice: the thought about the lowest stat that some thought covers."""
    for stat, _ in sorted(state.to_dict().items(), key=lambda kv: kv[1]):
        for t in THOUGHTS.values():
            if t.stat == stat:
                return t.name
    return next(iter(THOUGHTS))
