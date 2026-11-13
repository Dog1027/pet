"""State -> action: handled by the LLM.

A Brain only takes the state and returns the LLM's raw text. It makes no judgement;
checking whether the output is correct is the supervisor's job.
"""
import json
import random
from abc import ABC, abstractmethod

from .actions import ACTIONS, safe_action
from .config import GeminiConfig
from .state import STAT_DESCRIPTIONS, PetState

SYSTEM_PROMPT = """You are the brain of a virtual pet. Based on the pet's six current stats (0-100, higher is better), choose the single most sensible next action.

Stats:
{stats}

Available actions (choose only from these, using the exact name):
{actions}

Output only one JSON object and nothing else:
{output_format}"""

# Normal runs only need the action; debug mode also asks for a reason
OUTPUT_FORMAT = '{"action": "<action name>"}'
OUTPUT_FORMAT_DEBUG = '{"action": "<action name>", "reason": "<one short sentence>"}'


def build_system_prompt(debug: bool = False) -> str:
    stats = "\n".join(f"- {k}: {v}" for k, v in STAT_DESCRIPTIONS.items())
    actions = "\n".join(
        f"- {a.name} ({a.label}): {a.description}; effect approx. {a.preview()}"
        for a in ACTIONS.values()
    )
    output_format = OUTPUT_FORMAT_DEBUG if debug else OUTPUT_FORMAT
    return SYSTEM_PROMPT.format(stats=stats, actions=actions, output_format=output_format)


def build_user_prompt(state: PetState, feedback: str | None = None) -> str:
    msg = "Current stats: " + json.dumps(state.to_dict())
    if feedback:
        msg += f"\n\nYour previous output was rejected by the supervisor. Reason: {feedback}\nPlease choose again."
    return msg


class Brain(ABC):
    @abstractmethod
    def decide(self, state: PetState, feedback: str | None = None) -> str:
        """Return the LLM's raw output string."""


class GeminiBrain(Brain):
    def __init__(self, cfg: GeminiConfig, debug: bool = False):
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
        self.system = build_system_prompt(debug)
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

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.last_model = "mock"

    def decide(self, state: PetState, feedback: str | None = None) -> str:
        r = random.random()
        if feedback is None and r < 0.10:
            return "I think it should go eat"   # not JSON
        if feedback is None and r < 0.20:
            return self._out("fly", "wants to fly")      # action doesn't exist
        if feedback is None and r < 0.30:
            return self._out("eat", "whatever")          # may not make sense
        pick = safe_action(state)
        return self._out(pick, f"restore {ACTIONS[pick].restores}")

    def _out(self, action: str, reason: str) -> str:
        obj = {"action": action, "reason": reason} if self.debug else {"action": action}
        return json.dumps(obj)
