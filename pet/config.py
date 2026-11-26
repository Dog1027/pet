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
class OllamaConfig:
    host: str = "http://localhost:11434"
    model: str = "hf.co/AtomicChat/Inkling-2-Mini-Uncensored-GGUF:IQ3_S"
    timeout: float = 30.0        # max seconds to wait per request (the first one also loads the model)


@dataclass
class MemoryConfig:
    time_scale: float = 1.0   # timestamps shown to the LLM = real seconds since the action * this
    forgetting: str = "chars" # forgetting method: chars / ebbinghaus / llm (see forgetting.py)
    # chars
    fade_start: float = 0.5   # entries past this share of the memory start losing characters
    fade_max: float = 0.8     # share of characters deleted from the oldest entry
    # ebbinghaus
    importance: float = 0.5           # importance given to every entry (higher = remembered longer)
    retention_threshold: float = 0.3  # retention below this -> the entry turns vague
    drop_threshold: float = 0.1       # retention below this -> the entry is dropped
    # llm
    forget_model: str = "gemma-4-26b-a4b-it"  # model asked to rewrite the memory


@dataclass
class Config:
    brain: str = "ollama"     # which model picks the actions: ollama / gemini
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)


def load(path: str | Path = DEFAULT_PATH) -> Config:
    path = Path(path)
    cfg = Config()
    if not path.exists():
        return cfg
    with path.open("rb") as f:
        doc = tomllib.load(f)

    cfg.brain = doc.get("brain", cfg.brain)

    data = doc.get("ollama", {})
    o = cfg.ollama
    o.host = data.get("host", o.host).rstrip("/")
    o.model = data.get("model", o.model)
    o.timeout = float(data.get("timeout", o.timeout))

    data = doc.get("gemini", {})
    g = cfg.gemini
    g.api_key = data.get("api_key") or None
    g.model = data.get("model", g.model)
    g.fallback_models = list(data.get("fallback_models", g.fallback_models))
    g.thinking_level = data.get("thinking_level", g.thinking_level)
    g.timeout = float(data.get("timeout", g.timeout))

    data = doc.get("memory", {})
    m = cfg.memory
    m.time_scale = float(data.get("time_scale", m.time_scale))
    m.fade_start = float(data.get("fade_start", m.fade_start))
    m.fade_max = float(data.get("fade_max", m.fade_max))
    m.forgetting = data.get("forgetting", m.forgetting)
    m.importance = float(data.get("importance", m.importance))
    m.retention_threshold = float(data.get("retention_threshold", m.retention_threshold))
    m.drop_threshold = float(data.get("drop_threshold", m.drop_threshold))
    m.forget_model = data.get("forget_model", m.forget_model)
    return cfg
