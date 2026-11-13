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


@dataclass
class Config:
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    # Memory timestamps shown to the LLM = real seconds since the action * this factor
    memory_time_scale: float = 1.0


def load(path: str | Path = DEFAULT_PATH) -> Config:
    path = Path(path)
    cfg = Config()
    if not path.exists():
        return cfg
    with path.open("rb") as f:
        doc = tomllib.load(f)

    data = doc.get("gemini", {})
    g = cfg.gemini
    g.api_key = data.get("api_key") or None
    g.model = data.get("model", g.model)
    g.fallback_models = list(data.get("fallback_models", g.fallback_models))
    g.thinking_level = data.get("thinking_level", g.thinking_level)
    g.timeout = float(data.get("timeout", g.timeout))

    cfg.memory_time_scale = float(doc.get("memory", {}).get("time_scale", cfg.memory_time_scale))
    return cfg
