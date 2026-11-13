"""The pet's memory of previous ticks, as shown to the LLM.

Each entry is an action and its result text. Entries in the older part of the memory fade:
some characters of the result are deleted, more the further back they are.
The action name is never forgotten.
"""
import random
import time
from collections import deque
from dataclasses import dataclass

from .config import MemoryConfig


@dataclass
class _Entry:
    at: float           # real time the entry was stored (time.monotonic())
    action: str         # never fades
    result: str         # fades with age
    order: list[int]    # fixed random order in which the result's characters are deleted


class Memory:
    def __init__(self, size: int, cfg: MemoryConfig):
        self.size = size
        self.cfg = cfg
        self._entries: deque[_Entry] = deque(maxlen=size)  # oldest first

    def add(self, action: str, result: str) -> None:
        order = list(range(len(result)))
        random.shuffle(order)
        self._entries.append(_Entry(time.monotonic(), action, result, order))

    def fade_ratio(self, index: int) -> float:
        """Share of the result's characters deleted for the entry at `index` (0 = most recent).

        Position = (index + 1) / size. Up to fade_start nothing fades; from there the
        ratio grows linearly and reaches fade_max at the oldest slot."""
        position = (index + 1) / self.size
        start = self.cfg.fade_start
        if position <= start or start >= 1:
            return 0.0
        return (position - start) / (1 - start) * self.cfg.fade_max

    def recall(self) -> list[tuple[float, str]]:
        """(seconds ago * time_scale, "action|result" with forgotten characters deleted),
        most recent first."""
        now = time.monotonic()
        out = []
        for index, e in enumerate(reversed(self._entries)):
            # The same characters stay deleted as the entry ages; more are removed each step
            gone = set(e.order[:round(self.fade_ratio(index) * len(e.result))])
            result = "".join(c for i, c in enumerate(e.result) if i not in gone)
            out.append(((now - e.at) * self.cfg.time_scale, f"{e.action}|{result}"))
        return out
