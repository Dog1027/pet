"""The pet's memory of previous ticks, as shown to the LLM.

Each entry is an action and its result text. The action name is always kept;
how the result degrades with age is decided by forgetting.py.
"""
import random
import time
from collections import deque
from dataclasses import dataclass

from .config import MemoryConfig
from .forgetting import forget


@dataclass
class _Entry:
    at: float       # real time the entry was stored (time.monotonic())
    action: str     # never forgotten
    result: str     # original result text; forgetting is applied on recall
    seed: int       # fixed per entry, passed to forget() for consistent randomness


class Memory:
    def __init__(self, size: int, cfg: MemoryConfig):
        self.size = size
        self.cfg = cfg
        self._entries: deque[_Entry] = deque(maxlen=size)  # oldest first

    def add(self, action: str, result: str) -> None:
        self._entries.append(_Entry(time.monotonic(), action, result, random.getrandbits(32)))

    def recall(self) -> list[tuple[float, str]]:
        """(seconds ago * time_scale, "action|result as remembered now"), most recent first."""
        now = time.monotonic()
        out = []
        for index, e in enumerate(reversed(self._entries)):
            position = (index + 1) / self.size  # in (0, 1]; 1 = the oldest slot
            result = forget(e.result, position, e.seed, self.cfg)
            out.append(((now - e.at) * self.cfg.time_scale, f"{e.action}|{result}"))
        return out
