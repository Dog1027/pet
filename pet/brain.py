"""Thoughts -> action: handled by the LLM.

A Brain takes the pet's current thought and its memory and returns the LLM's raw text.
The LLM never sees the stats' numbers; the thought is worked out in thoughts.py.
"""
import json
import random
import urllib.request
from abc import ABC, abstractmethod
from typing import Sequence

from .actions import llm_choices
from .config import Config, GeminiConfig, OllamaConfig


def build_prompt(thought: str, memory: Sequence[str] = ()) -> str:
    """The whole prompt: the names of the actions the pet can do (no descriptions: what they do
    it learns from its memory, where each action says what came of it), how it feels now, and
    what it did lately. The names come in a new random order each time, so the first one
    doesn't always win. The reply format comes from response_schema().
    memory: the lines from Memory.recall(), most recent first."""
    names = llm_choices()
    random.shuffle(names)
    mem = "\n".join(memory) if memory else "(empty)"
    return (
        "You are a small pet rabbit. Pick what to do next, by how you feel now. Learn from what"
        " you did lately: don't keep doing what didn't help.\n\n"
        f"What you can do: {', '.join(names)}\n\n"
        f"How you feel now: {thought}\n\n"
        "What you did lately (most recent first; how long ago | what you did: what came of it"
        " | how you felt before > after):\n"
        f"{mem}"
    )


def response_schema() -> dict:
    """JSON schema the reply must follow: {"action": <one name from the action list>}."""
    return {
        "type": "object",
        "properties": {"action": {"type": "string", "enum": llm_choices()}},
        "required": ["action"],
    }


def parse(raw: str) -> str | None:
    """Read the action name out of the LLM's JSON reply ({"action": "<name>"}).
    Returns None if the reply isn't valid JSON or the name isn't an action the LLM may pick."""
    try:
        name = json.loads(raw)["action"]
    except (ValueError, KeyError, TypeError):
        return None
    return name if name in llm_choices() else None


class Brain(ABC):
    @abstractmethod
    def decide(self, prompt: str) -> str:
        """Send the prompt (build_prompt) and return the LLM's raw output string."""


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
        self.last_model: str | None = None  # model that actually answered the last call

    def decide(self, prompt: str) -> str:
        """Try the main model, then the fallbacks; switch only on busy / timeout, re-raise anything else."""
        error: Exception | None = None
        self.last_model = None
        for model in self.models:
            try:
                interaction = self.client.interactions.create(
                    model=model,
                    input=prompt,
                    response_format={"type": "text", "mime_type": "application/json",
                                     "schema": response_schema()},
                    generation_config={"thinking_level": self.thinking_level},
                    store=False,  # each decision is independent; no need to keep the conversation server-side
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


class OllamaBrain(Brain):
    """Local model served by Ollama.

    The prompt is built here in the model's own chat format and sent with raw=True: the Ollama
    model's template is a Jinja (Hugging Face) one Ollama can't use, and its stop list contains
    <|content_text|>, the first token of every reply, so the normal chat API always returns ''.
    Thinking is turned off (effort 0) and the reply is constrained to response_schema().
    """

    def __init__(self, cfg: OllamaConfig):
        self.cfg = cfg
        self.last_model = cfg.model

    def decide(self, prompt: str) -> str:
        prompt = (
            "<|message_system|><|content_text|>Thinking effort level: 0<|end_message|>"
            f"<|message_user|><|content_text|>{prompt}<|end_message|>"
            "<|message_model|><|content_text|>"
        )
        body = {
            "model": self.cfg.model,
            "prompt": prompt,
            "raw": True,
            "stream": False,
            "format": response_schema(),
            "options": {"stop": ["<|end_message|>", "<|content_model_end_sampling|>"], "num_predict": 64},
        }
        request = urllib.request.Request(
            f"{self.cfg.host}/api/generate",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.cfg.timeout) as response:
            return json.load(response).get("response", "")


class MockBrain(Brain):
    """Fake brain that doesn't call any API: picks a random action. For testing the loop."""

    last_model = "mock"

    def decide(self, prompt: str) -> str:
        return json.dumps({"action": random.choice(llm_choices())})


def make_brain(cfg: Config, mock: bool = False) -> Brain:
    """The brain chosen by `brain` in the config (or the fake one when mock is True).
    Raises ValueError for an unknown name."""
    if mock:
        return MockBrain()
    brains = {"ollama": lambda: OllamaBrain(cfg.ollama), "gemini": lambda: GeminiBrain(cfg.gemini)}
    if cfg.brain not in brains:
        raise ValueError(f"unknown brain {cfg.brain!r} in the config; choose from {sorted(brains)}")
    return brains[cfg.brain]()
