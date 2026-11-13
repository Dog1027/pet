"""The pet's memory of previous ticks, as shown to the LLM.

Each entry is one line of text. Entries in the older part of the memory fade:
some of their characters are replaced by FADE_CHAR, more the further back they are.
"""
import random
import time
from collections import deque
from dataclasses import dataclass

from .config import MemoryConfig

FADE_CHAR = ","  # what a forgotten character turns into


@dataclass
class _Entry:
    at: float           # real time the entry was stored (time.monotonic())
    text: str
    order: list[int]    # fixed random order in which this entry's characters disappear


class Memory:
    def __init__(self, size: int, cfg: MemoryConfig):
        self.size = size
        self.cfg = cfg
        self._entries: deque[_Entry] = deque(maxlen=size)  # oldest first

    def add(self, text: str) -> None:
        order = list(range(len(text)))
        random.shuffle(order)
        self._entries.append(_Entry(time.monotonic(), text, order))

    def fade_ratio(self, index: int) -> float:
        """Share of characters blanked for the entry at `index` (0 = most recent).

        Position = (index + 1) / size. Up to fade_start nothing fades; from there the
        ratio grows linearly and reaches fade_max at the oldest slot."""
        position = (index + 1) / self.size
        start = self.cfg.fade_start
        if position <= start or start >= 1:
            return 0.0
        return (position - start) / (1 - start) * self.cfg.fade_max

    def recall(self) -> list[tuple[float, str]]:
        """(seconds ago * time_scale, text with forgotten characters replaced), most recent first."""
        now = time.monotonic()
        out = []
        for index, e in enumerate(reversed(self._entries)):
            chars = list(e.text)
            # The same characters stay blank as the entry ages; more are added each step
            for i in e.order[:round(self.fade_ratio(index) * len(chars))]:
                chars[i] = FADE_CHAR
            out.append(((now - e.at) * self.cfg.time_scale, "".join(chars)))
        return out
