"""Thoughts -> action: handled by the LLM.

A Brain takes the pet's current thoughts and its memory and returns the LLM's raw text.
The LLM never sees the stats' numbers; the thoughts are worked out in thoughts.py.
"""
import json
import random
from abc import ABC, abstractmethod
from typing import Mapping, Sequence

from .actions import ACTIONS
from .config import GeminiConfig


def build_prompt(thoughts: Mapping[str, str], memory: Sequence[tuple[float, str]] = ()) -> str:
    """The whole prompt: the current thoughts, then the memory of previous ticks.
    The action list and the reply format come from response_schema(), not the prompt.
    thoughts: {name: strength}; memory: (seconds ago, text) per remembered tick, most recent first."""
    th = ",\n".join(f"{name}: {level}" for name, level in thoughts.items()) if thoughts else "(none)"
    mem = "\n".join(f"-{round(age)}s|{text}" for age, text in memory) if memory else "(empty)"
    return f"Thoughts:\n{th}\n\nMemory:\n{mem}"


def response_schema() -> dict:
    """JSON schema the reply must follow: {"action": <one name from the action list>}."""
    return {
        "type": "object",
        "properties": {"action": {"type": "string", "enum": list(ACTIONS)}},
        "required": ["action"],
    }


def parse(raw: str) -> str | None:
    """Read the action name out of the LLM's JSON reply ({"action": "<name>"}).
    Returns None if the reply isn't valid JSON or the name isn't a registered action."""
    try:
        name = json.loads(raw)["action"]
    except (ValueError, KeyError, TypeError):
        return None
    return name if name in ACTIONS else None


class Brain(ABC):
    @abstractmethod
    def decide(self, thoughts: Mapping[str, str], memory: Sequence[tuple[float, str]] = ()) -> str:
        """Return the LLM's raw output string."""


class GeminiBrain(Brain):
    def __init__(self, cfg: GeminiConfig):
        from google import genai  # lazy import so mock mode doesn't load the SDK
        from google.genai import types

        # When api_key is None the SDK reads GEMINI_API_KEY / GOOGLE_API_KEY instead.
        # The SDK's built-in retries are turned off (by default they silently retry for a long time);
        # a busy model is handled by the fallback models instead.
        self.client = genai.Client(
            api_key=cfg.api_key,
            http_options=types.HttpOptions(
                timeout=int(cfg.timeout * 1000),  # milliseconds
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        self.models = [cfg.model, *cfg.fallback_models]
        self.thinking_level = cfg.thinking_level
        self.last_model: str | None = None  # model that actually answered this tick

    def decide(self, thoughts: Mapping[str, str], memory: Sequence[tuple[float, str]] = ()) -> str:
        """Try the main model, then the fallbacks; switch only on busy / timeout, re-raise anything else."""
        error: Exception | None = None
        self.last_model = None
        for model in self.models:
            try:
                interaction = self.client.interactions.create(
                    model=model,
                    input=build_prompt(thoughts, memory),
                    response_format={"type": "text", "mime_type": "application/json",
                                     "schema": response_schema()},
                    generation_config={"thinking_level": self.thinking_level},
                    store=False,  # each tick is independent; no need to keep the conversation server-side
                )
            except Exception as e:
                if not _is_transient(e):
                    raise
                print(f"   [LLM] {model} is unavailable ({_short(e)}), trying the next model")
                error = e
                continue
            self.last_model = model
            return interaction.output_text or ""
        raise RuntimeError("all models are unavailable") from error


def _is_transient(e: Exception) -> bool:
    """Busy (429 / 5xx), timeout or connection problem -> worth trying another model."""
    code = getattr(e, "status_code", None)
    if code in (429, 500, 502, 503, 504):
        return True
    return any(k in type(e).__name__ for k in ("Timeout", "Connection"))


def _short(e: Exception) -> str:
    code = getattr(e, "status_code", None)
    return f"HTTP {code}" if code else type(e).__name__


class MockBrain(Brain):
    """Fake brain that doesn't call any API: picks a random action. For testing the loop."""

    last_model = "mock"

    def decide(self, thoughts: Mapping[str, str], memory: Sequence[tuple[float, str]] = ()) -> str:
        return json.dumps({"action": random.choice(list(ACTIONS))})
