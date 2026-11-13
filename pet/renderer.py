"""Display layer. Text for now; to switch to graphics later, implement a new Renderer.
The main loop doesn't need to change."""
from abc import ABC, abstractmethod

from .actions import Action
from .state import PetState


class Renderer(ABC):
    @abstractmethod
    def show_action(self, pet_name: str, action: Action, reason: str, fallback: bool) -> None: ...

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

    def show_action(self, pet_name, action, reason, fallback):
        tag = " (decided by the supervisor)" if fallback else ""
        print(f"\n🐾 {pet_name} decides to [{action.label}]{tag}")
        print(f"   {action.text}")
        if self.debug and reason:
            print(f"   [debug] reason: {reason}")

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
