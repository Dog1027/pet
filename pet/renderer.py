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
    def show_action(self, pet_name: str, action: Action, thought: str, fallback: bool,
                    applied: bool = True) -> None:
        """thought: the thought that led to this action.
        applied=False: the action's condition blocked its effect this tick."""

    @abstractmethod
    def show_state(self, state: PetState, delta: dict[str, int]) -> None: ...

    def show_supervisor(self, attempt: int, ok: bool, errors: list[str], warnings: list[str]) -> None:
        pass

    def show_debug(self, attempt: int, model: str | None, raw: str) -> None:
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

    def show_action(self, pet_name, action, thought, fallback, applied=True):
        tag = " (decided by the supervisor)" if fallback else ""
        print(f"\n🐾 {pet_name} decides to [{action.label}]{tag}")
        if not applied:
            print("   ...but it has no effect this time")
        if self.debug and not applied:
            print(f"   [debug] condition {action.condition.__name__} returned False")
        if self.debug:
            print(f"   [debug] thought: {thought} -> action: {action.name}")

    def show_debug(self, attempt, model, raw):
        if self.debug:
            print(f"   [debug #{attempt}] model={model} raw={raw.strip()!r}")

    def show_state(self, state, delta):
        for k, v in state.to_dict().items():
            d = delta.get(k, 0)
            ds = f"{d:+d}" if d else ""
            print(f"   {k:<12} {_bar(v)} {v:>3} {ds}")

    def show_supervisor(self, attempt, ok, errors, warnings):
        mark = "✅" if ok else "❌"
        msg = "passed" if ok else "; ".join(errors)
        print(f"   [supervisor #{attempt}] {mark} {msg}")
        for w in warnings:
            print(f"   [supervisor #{attempt}] ⚠️  {w}")
