"""The pet's memory of previous ticks, as shown to the LLM.

Each entry is an action and its result text. Entries are stored complete;
how they degrade with age is decided by forgetting.py each time they are recalled.
"""
import random
import time
from collections import deque
from dataclasses import dataclass

from .config import GeminiConfig, MemoryConfig
from .forgetting import Item, forget


@dataclass
class _Entry:
    at: float       # real time the entry was stored (time.monotonic())
    action: str
    result: str     # original result text; forgetting is applied on recall
    seed: int       # fixed per entry, for forgetting methods that need consistent randomness


class Memory:
    def __init__(self, size: int, cfg: MemoryConfig, gemini: GeminiConfig):
        self.size = size
        self.cfg = cfg
        self.gemini = gemini  # only used by the "llm" forgetting method
        self._entries: deque[_Entry] = deque(maxlen=size)  # oldest first

    def add(self, action: str, result: str) -> None:
        self._entries.append(_Entry(time.monotonic(), action, result, random.getrandbits(32)))

    def recall(self) -> list[str]:
        """The memory lines as remembered now ("-<seconds ago * time_scale>s|action|result"),
        most recent first."""
        now = time.monotonic()
        items = [
            Item(
                age=(now - e.at) * self.cfg.time_scale,
                action=e.action,
                result=e.result,
                seed=e.seed,
                position=(index + 1) / self.size,  # in (0, 1]; 1 = the oldest slot
            )
            for index, e in enumerate(reversed(self._entries))
        ]
        return forget(items, self.cfg, self.gemini)
