"""Forgetting: how a remembered result degrades as it gets older.

This module is the one place that decides what forgetting looks like.
Memory (memory.py) only calls forget() for every entry each time it is recalled;
to redesign forgetting, change forget() and keep its signature.

Current behaviour: entries in the first fade_start share of the memory are intact.
After that, a linearly growing share of the result's characters is deleted,
reaching fade_max at the oldest slot.
"""
import random

from .config import MemoryConfig


def forget(result: str, position: float, seed: int, cfg: MemoryConfig) -> str:
    """Return the result text as the pet remembers it now.

    result:   the original, complete result text of the entry
    position: where the entry sits in the memory, in (0, 1]:
              close to 0 = most recent, 1 = the oldest slot
    seed:     fixed per entry; use it for any randomness so the same entry
              degrades consistently from one recall to the next
    cfg:      the [memory] settings from config.toml
    """
    ratio = fade_ratio(position, cfg)
    if ratio <= 0:
        return result
    # Fixed random order per entry: characters that are gone stay gone as the entry ages
    order = list(range(len(result)))
    random.Random(seed).shuffle(order)
    gone = set(order[:round(ratio * len(result))])
    return "".join(c for i, c in enumerate(result) if i not in gone)


def fade_ratio(position: float, cfg: MemoryConfig) -> float:
    """Share of characters deleted at this position."""
    start = cfg.fade_start
    if position <= start or start >= 1:
        return 0.0
    return (position - start) / (1 - start) * cfg.fade_max
