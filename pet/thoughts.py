"""Thoughts: what the LLM chooses from, and the decision trees that turn a thought into an action.

Flow:  stats -> (LLM) thought -> (decision tree, code) action -> (code) stats change

The LLM only ever sees the list of thought names. Each thought has a decision function
that receives the current state and returns the name of the action to perform.
For now every tree maps straight to one action; extend them with conditions later:

    @thought("eat")
    def decide_eat(state: PetState) -> str:
        if not has_food():            # your own condition
            return "ask_for_food"     # any action registered in actions.py
        return "eat"

To add a thought, write a decision function and decorate it with @thought(...).
The LLM prompt picks it up automatically.
"""
import json
from dataclasses import dataclass
from typing import Callable

from .actions import ACTIONS
from .state import PetState

DecideFn = Callable[[PetState], str]


@dataclass(frozen=True)
class Thought:
    name: str            # what the LLM outputs
    decide: DecideFn     # decision tree: state -> action name


THOUGHTS: dict[str, Thought] = {}


def thought(name: str) -> Callable[[DecideFn], DecideFn]:
    """Register a thought and its decision tree."""
    def register(fn: DecideFn) -> DecideFn:
        if name in THOUGHTS:
            raise ValueError(f"thought {name} is registered twice")
        THOUGHTS[name] = Thought(name, fn)
        return fn
    return register


# ---------------------------------------------------------------- decision trees

@thought("eat")
def decide_eat(state: PetState) -> str:
    return "eat"


@thought("sleep")
def decide_sleep(state: PetState) -> str:
    return "sleep"


@thought("play")
def decide_play(state: PetState) -> str:
    return "play"


@thought("bathe")
def decide_bathe(state: PetState) -> str:
    return "bathe"


@thought("cuddle")
def decide_cuddle(state: PetState) -> str:
    return "seek_attention"


@thought("rest")
def decide_rest(state: PetState) -> str:
    return "rest"


@thought("nothing")
def decide_nothing(state: PetState) -> str:
    return "idle"


# ---------------------------------------------------------------- parse / resolve

def parse(raw: str) -> str | None:
    """Read the thought name out of the LLM's JSON reply ({"thought": "<name>"}).
    Returns None if the reply isn't valid JSON or the name isn't in the list."""
    try:
        name = json.loads(raw)["thought"]
    except (ValueError, KeyError, TypeError):
        return None
    return name if name in THOUGHTS else None


def resolve(thought_name: str, state: PetState) -> str:
    """Run the thought's decision tree and return the action name it picked."""
    action_name = THOUGHTS[thought_name].decide(state)
    if action_name not in ACTIONS:
        raise ValueError(f"thought {thought_name} resolved to unknown action {action_name!r}")
    return action_name
