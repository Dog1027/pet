"""Load config.toml."""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config.toml"


@dataclass
class GeminiConfig:
    api_key: str | None = None   # None -> the SDK reads GEMINI_API_KEY / GOOGLE_API_KEY
    model: str = "gemini-3.5-flash-lite"
    fallback_models: list[str] = field(default_factory=lambda: ["gemini-3.8-flash"])
    thinking_level: str = "low"
    timeout: float = 20.0        # max seconds to wait per request


def load(path: str | Path = DEFAULT_PATH) -> GeminiConfig:
    path = Path(path)
    cfg = GeminiConfig()
    if not path.exists():
        return cfg
    with path.open("rb") as f:
        data = tomllib.load(f).get("gemini", {})
    cfg.api_key = data.get("api_key") or None
    cfg.model = data.get("model", cfg.model)
    cfg.fallback_models = list(data.get("fallback_models", cfg.fallback_models))
    cfg.thinking_level = data.get("thinking_level", cfg.thinking_level)
    cfg.timeout = float(data.get("timeout", cfg.timeout))
    return cfg
