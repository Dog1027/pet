"""Stats -> thought: handled by the LLM.

A Brain only takes the state and returns the LLM's raw text. It makes no judgement;
checking whether the output is correct is the supervisor's job, and turning the
thought into an action is the decision tree's job (thoughts.py).
"""
import json
import random
from abc import ABC, abstractmethod

from .config import GeminiConfig
from .state import PetState
from .thoughts import THOUGHTS, safe_thought

SYSTEM_PROMPT = """You are a virtual pet. Given your stats (0-100, higher is better), pick the one thought that fits best.

Thoughts:
{thoughts}

Reply with only the thought's name, nothing else."""


def build_system_prompt() -> str:
    thoughts = "\n".join(f"- {t.name}: {t.description}" for t in THOUGHTS.values())
    return SYSTEM_PROMPT.format(thoughts=thoughts)


def build_user_prompt(state: PetState, feedback: str | None = None) -> str:
    msg = json.dumps(state.to_dict())
    if feedback:
        msg += f"\n\nYour previous reply was rejected: {feedback}\nPick again."
    return msg


class Brain(ABC):
    @abstractmethod
    def decide(self, state: PetState, feedback: str | None = None) -> str:
        """Return the LLM's raw output string."""


class GeminiBrain(Brain):
    def __init__(self, cfg: GeminiConfig):
        from google import genai  # lazy import so mock mode doesn't load the SDK
        from google.genai import types

        # When api_key is None the SDK reads GEMINI_API_KEY / GOOGLE_API_KEY instead.
        # The SDK's built-in retries are turned off (by default they silently retry for a long time);
        # retries are handled by the supervisor loop and the fallback models.
        self.client = genai.Client(
            api_key=cfg.api_key,
            http_options=types.HttpOptions(
                timeout=int(cfg.timeout * 1000),  # milliseconds
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        self.models = [cfg.model, *cfg.fallback_models]
        self.thinking_level = cfg.thinking_level
        self.system = build_system_prompt()
        self.last_model: str | None = None  # model that actually answered this tick

    def decide(self, state: PetState, feedback: str | None = None) -> str:
        """Try the main model, then the fallbacks; switch only on busy / timeout, re-raise anything else."""
        error: Exception | None = None
        self.last_model = None
        for model in self.models:
            try:
                interaction = self.client.interactions.create(
                    model=model,
                    system_instruction=self.system,
                    input=build_user_prompt(state, feedback),
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
            return interaction.output_text or ""  # an empty string is rejected by the supervisor
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
    """Fake brain that doesn't call any API, for testing the loop and the supervisor.
    It deliberately produces some bad outputs."""

    last_model = "mock"

    def decide(self, state: PetState, feedback: str | None = None) -> str:
        r = random.random()
        if feedback is None and r < 0.10:
            return "I think it should go eat"   # extra text instead of just a name
        if feedback is None and r < 0.20:
            return "fly"                        # not in the thought list
        if feedback is None and r < 0.30:
            return "eat"                        # may not make sense
        return safe_thought(state)
