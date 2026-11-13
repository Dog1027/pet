"""Stats -> thought: handled by the LLM.

A Brain only takes the state and returns the LLM's raw text. Turning that into a
thought and then an action is done in thoughts.py.
"""
import json
import random
from abc import ABC, abstractmethod
from typing import Sequence

from .config import GeminiConfig
from .state import PetState
from .thoughts import THOUGHTS

def build_prompt(state: PetState, memory: Sequence[str] = ()) -> str:
    """The whole prompt: the current stats, then the memory of previous ticks.
    The thought list and the reply format come from response_schema(), not the prompt.
    memory: one plain-text line per previous tick, oldest first."""
    status = json.dumps(state.to_dict(), indent=4)
    mem = "\n".join(memory) if memory else "(empty)"
    return f"Status: {status}\n\nMemory:\n{mem}"


def response_schema() -> dict:
    """JSON schema the reply must follow: {"thought": <one name from the thought list>}."""
    return {
        "type": "object",
        "properties": {"thought": {"type": "string", "enum": list(THOUGHTS)}},
        "required": ["thought"],
    }


class Brain(ABC):
    @abstractmethod
    def decide(self, state: PetState, memory: Sequence[str] = ()) -> str:
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

    def decide(self, state: PetState, memory: Sequence[str] = ()) -> str:
        """Try the main model, then the fallbacks; switch only on busy / timeout, re-raise anything else."""
        error: Exception | None = None
        self.last_model = None
        for model in self.models:
            try:
                interaction = self.client.interactions.create(
                    model=model,
                    input=build_prompt(state, memory),
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
    """Fake brain that doesn't call any API: picks a random thought. For testing the loop."""

    last_model = "mock"

    def decide(self, state: PetState, memory: Sequence[str] = ()) -> str:
        return json.dumps({"thought": random.choice(list(THOUGHTS))})
