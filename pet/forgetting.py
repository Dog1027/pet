"""Forgetting: how the pet's memory degrades as it gets older.

Memory (memory.py) calls forget() with every stored entry each time it is recalled,
and gets back the lines shown to the LLM. Which method runs is chosen by
[memory] forgetting in config.toml, or --forgetting on the command line.

Methods:
    none        remembers everything as it was (the default)
    chars       deletes a growing share of the result's characters in older entries
    ebbinghaus  retention curve over time: clear -> vague -> dropped (ebbinghaus.py)
    llm         asks a model ([memory] forget_model) to rewrite the memory as the pet remembers it

To add a method, write a function and decorate it with @method("name"):

    @method("none")
    def keep_everything(items, cfg, gemini):
        return [line(i.age, i.action, i.result) for i in items]
"""
import json
import random
import re
from dataclasses import dataclass
from typing import Callable, Sequence

from .config import GeminiConfig, MemoryConfig
from .ebbinghaus import llm_forgetting_algorithm


@dataclass(frozen=True)
class Item:
    """One stored memory entry, as handed to a forgetting method."""
    age: float       # seconds since it was stored * time_scale
    action: str      # action name; the built-in methods never forget it
    result: str      # original, complete result text
    seed: int        # fixed per entry; use it for randomness that must stay consistent between recalls
    position: float  # place in the memory, in (0, 1]: close to 0 = most recent, 1 = the oldest slot


MethodFn = Callable[[Sequence[Item], MemoryConfig, GeminiConfig], list[str]]
METHODS: dict[str, MethodFn] = {}


def method(name: str) -> Callable[[MethodFn], MethodFn]:
    """Register a forgetting method."""
    def register(fn: MethodFn) -> MethodFn:
        if name in METHODS:
            raise ValueError(f"forgetting method {name} is registered twice")
        METHODS[name] = fn
        return fn
    return register


def line(age: float, action: str, result: str) -> str:
    """One memory line as shown to the LLM."""
    return f"-{round(age)}s|{action}|{result}"


def forget(items: Sequence[Item], cfg: MemoryConfig, gemini: GeminiConfig) -> list[str]:
    """Return the memory lines as the pet remembers them now, most recent first.
    items: every stored entry, most recent first."""
    if cfg.forgetting not in METHODS:
        raise ValueError(f"unknown forgetting method {cfg.forgetting!r}; choose from {sorted(METHODS)}")
    return METHODS[cfg.forgetting](items, cfg, gemini)


# ---------------------------------------------------------------- none

@method("none")
def forget_nothing(items: Sequence[Item], cfg: MemoryConfig, gemini: GeminiConfig) -> list[str]:
    """Remember every stored entry exactly as it was (the default)."""
    return [line(item.age, item.action, item.result) for item in items]


# ---------------------------------------------------------------- chars

@method("chars")
def forget_chars(items: Sequence[Item], cfg: MemoryConfig, gemini: GeminiConfig) -> list[str]:
    """Entries in the first fade_start share of the memory are intact. After that, a linearly
    growing share of the result's characters is deleted, reaching fade_max at the oldest slot."""
    out = []
    for item in items:
        ratio = fade_ratio(item.position, cfg)
        result = item.result
        if ratio > 0:
            # Fixed random order per entry: characters that are gone stay gone as the entry ages
            order = list(range(len(result)))
            random.Random(item.seed).shuffle(order)
            gone = set(order[:round(ratio * len(result))])
            result = "".join(c for i, c in enumerate(result) if i not in gone)
        out.append(line(item.age, item.action, result))
    return out


def fade_ratio(position: float, cfg: MemoryConfig) -> float:
    """Share of characters deleted at this position."""
    start = cfg.fade_start
    if position <= start or start >= 1:
        return 0.0
    return (position - start) / (1 - start) * cfg.fade_max


# ---------------------------------------------------------------- ebbinghaus

_EBBINGHAUS_LINE = re.compile(r"\[Time:\s*(\d+)\]\s*\[Importance:\s*[\d.]+\]\s*\[Access:\s*\d+\]\s*(?:\[FADED\]\s*)?(.*)")


@method("ebbinghaus")
def forget_ebbinghaus(items: Sequence[Item], cfg: MemoryConfig, gemini: GeminiConfig) -> list[str]:
    """Run llm_forgetting_algorithm() over the memory: each entry's retention decays with its age
    (in the pet's time, so time_scale matters). Below retention_threshold the entry is marked
    vague; below drop_threshold it is left out.
    Every entry gets the same importance ([memory] importance) and an access count of 1."""
    if not items:
        return []
    now = round(max(item.age for item in items))  # the algorithm wants whole, non-negative times
    memory_str = "\n".join(
        f"[Time: {now - round(item.age)}] [Importance: {cfg.importance}] [Access: 1] {item.action}|{item.result}"
        for item in items
    )
    kept = llm_forgetting_algorithm(memory_str, now, cfg.retention_threshold, cfg.drop_threshold)
    out = []
    for text in kept.split("\n"):
        match = _EBBINGHAUS_LINE.match(text)
        if match:
            out.append(f"-{now - int(match.group(1))}s|{match.group(2)}")
    return out


# ---------------------------------------------------------------- llm

LLM_INSTRUCTIONS = """\
These are a pet's memories, most recent first.
Each line is: -<seconds ago>s|<action>[: what came of it]|<thought before>><thought after>

The pet has a poor memory. Rewrite the list the way the pet remembers it now:
- the few most recent lines stay exactly as they are
- in older lines keep the time and the action, but make the part after the last | vague:
  shorten it, lose one side of it, or replace it with ?
- drop some of the oldest lines completely
With more than three lines, returning the list unchanged is wrong. Never add a line.
"""

_client = None  # created on first use, so the other methods never load the SDK


def llm_schema() -> dict:
    """JSON schema of the reply: {"memory": [<line>, ...]}."""
    return {
        "type": "object",
        "properties": {"memory": {"type": "array", "items": {"type": "string"}}},
        "required": ["memory"],
    }


@method("llm")
def forget_llm(items: Sequence[Item], cfg: MemoryConfig, gemini: GeminiConfig) -> list[str]:
    """Ask cfg.forget_model to rewrite the whole memory. One extra API call per recall.
    If the call fails or the reply is unusable, the memory is returned unforgotten."""
    original = [line(item.age, item.action, item.result) for item in items]
    if not original:
        return []
    try:
        reply = _llm_client(gemini).interactions.create(
            model=cfg.forget_model,
            input=LLM_INSTRUCTIONS + "\n" + "\n".join(original),
            response_format={"type": "text", "mime_type": "application/json", "schema": llm_schema()},
            store=False,
        )
        lines = json.loads(reply.output_text or "")["memory"]
        lines = [text.strip() for text in lines if isinstance(text, str) and text.strip()]
    except Exception as e:  # API error or unusable reply: remember everything this time
        print(f"   [forgetting] {cfg.forget_model} failed ({type(e).__name__}), memory left as is")
        return original
    return lines[:len(original)]  # never more lines than were stored


def _llm_client(gemini: GeminiConfig):
    global _client
    if _client is None:
        from google import genai
        from google.genai import types

        _client = genai.Client(
            api_key=gemini.api_key,
            http_options=types.HttpOptions(
                timeout=int(gemini.timeout * 1000),  # milliseconds
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
    return _client
