"""Display layer. Text for now; to switch to graphics later, implement a new Renderer.
The main loop doesn't need to change."""
import sys
from abc import ABC, abstractmethod

from .actions import Action
from .state import PetState


class Renderer(ABC):
    def begin_tick(self, tick: int) -> None:
        """Called at the start of every tick."""
        pass

    @abstractmethod
    def show_thoughts(self, thoughts: dict[str, str]) -> None:
        """What the pet is feeling this tick: {name: strength}."""
        pass

    @abstractmethod
    def show_action(self, pet_name: str, action: Action, applied: bool = True) -> None:
        """applied=False: the action's condition blocked its effect this tick."""

    @abstractmethod
    def show_state(self, state: PetState, delta: dict[str, int]) -> None: ...

    @abstractmethod
    def show_no_action(self, pet_name: str, raw: str) -> None:
        """The LLM's reply wasn't an action from the list, so nothing happens this tick."""

    def show_debug(self, model: str | None, raw: str) -> None:
        """Debug mode only: what the LLM actually returned."""
        pass


def _bar(v: int, width: int = 20) -> str:
    n = round(v / 100 * width)
    return "█" * n + "░" * (width - n)


class TextRenderer(Renderer):
    def __init__(self, debug: bool = False):
        self.debug = debug
        # Normal mode keeps only the current tick on screen; debug mode keeps the full history.
        # Only clear on a real terminal, so piped output / logs stay readable.
        self.clear_each_tick = not debug and sys.stdout.isatty()

    def begin_tick(self, tick):
        if self.clear_each_tick:
            print("\033[2J\033[H", end="")  # clear screen, cursor to top-left
        print(f"\n--- Tick {tick} ---")

    def show_thoughts(self, thoughts):
        text = ", ".join(f"{name} ({level})" for name, level in thoughts.items()) or "none"
        print(f"   thoughts: {text}")

    def show_action(self, pet_name, action, applied=True):
        print(f"\n🐾 {pet_name} decides to [{action.label}]")
        if not applied:
            print("   ...but it has no effect this time")
        if self.debug and not applied:
            print(f"   [debug] condition {action.condition.__name__} returned False")

    def show_no_action(self, pet_name, raw):
        print(f"\n🐾 {pet_name} does nothing (unusable reply: {raw.strip()!r})")

    def show_debug(self, model, raw):
        if self.debug:
            print(f"   [debug] model={model} raw={raw.strip()!r}")

    def show_state(self, state, delta):
        for k, v in state.to_dict().items():
            d = delta.get(k, 0)
            ds = f"{d:+d}" if d else ""
            print(f"   {k:<12} {_bar(v)} {v:>3} {ds}")
