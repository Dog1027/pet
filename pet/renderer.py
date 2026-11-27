"""Display layer. The engine (engine.py) calls these as things happen.
A display implements its own Renderer (see webui/server.py)."""
from abc import ABC, abstractmethod

from .actions import Action
from .interactions import Interaction
from .state import PetState
from .world import World


class Renderer(ABC):
    @abstractmethod
    def show_thought(self, thought: str) -> None:
        """The pet starts thinking about its next action; this is what is on its mind."""

    def show_prompt(self, prompt: str) -> None:
        """What is about to be sent to the LLM (debug displays only)."""

    def show_debug(self, model: str | None, raw: str) -> None:
        """What the LLM actually returned (debug displays only)."""

    @abstractmethod
    def show_action(self, pet_name: str, action: Action, chosen_by: str) -> None:
        """The pet starts an action. chosen_by: who picked it (the previous action's name,
        "reflex: ...", "llm" or "owner_<interaction>")."""

    def show_action_done(self, pet_name: str, action: Action, interrupted: bool = False) -> None:
        """The action has finished, or (interrupted=True) an owner interaction cut it short."""

    @abstractmethod
    def show_no_action(self, pet_name: str, raw: str) -> None:
        """The LLM's reply wasn't an action from the list; the pet will ask again shortly."""

    def show_interaction(self, pet_name: str, item: Interaction, delta: dict[str, float]) -> None:
        """The owner did something; delta is the actual change (stats and world)."""

    def show_state(self, state: PetState, world: World, delta: dict[str, float]) -> None:
        """Called after the owner interacts; delta is what that changed."""

    def show_note(self, text: str) -> None:
        """Anything else worth telling (errors, the pet falling ill)."""


def signed(v: float) -> str:
    """+1 for whole numbers (positions), +3.6 for the rest."""
    return f"{v:+d}" if isinstance(v, int) else f"{v:+.1f}"


def changes(delta: dict[str, float]) -> str:
    return ", ".join(f"{k} {signed(v)}" for k, v in delta.items()) or "no change"
