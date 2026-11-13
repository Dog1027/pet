"""Supervise whether the LLM's output is correct.

Three levels of checks:
1. Format: is the reply just a single name?
2. Validity: is that name in the thought list?
3. Sanity: does the thought make sense for the current stats? (rule-based)

Every verdict is written to a JSONL log so the LLM's accuracy can be analysed later.
"""
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .state import PetState
from .thoughts import THOUGHTS

FULL = 90          # a stat >= this counts as "already full"
CRITICAL = 20      # a stat < this counts as "critical"


@dataclass
class Verdict:
    ok: bool
    thought: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def feedback(self) -> str:
        return "; ".join(self.errors)


def _normalize(raw: str) -> str:
    """Tolerate harmless wrapping: whitespace, quotes, backticks, a trailing period, capitals."""
    return raw.strip().strip("`\"'.").strip().lower()


def check(raw: str, state: PetState) -> Verdict:
    names = ", ".join(THOUGHTS)

    # 1. Format
    name = _normalize(raw)
    if not name:
        return Verdict(False, errors=["empty output"])
    if len(name.split()) != 1:
        return Verdict(False, errors=[f"reply with only one name from: {names}"])

    # 2. Validity
    if name not in THOUGHTS:
        return Verdict(False, name, errors=[f"'{name}' is not in the list: {names}"])

    v = Verdict(True, name)
    s = state.to_dict()

    # 3. Sanity
    critical = {k: val for k, val in s.items() if val < CRITICAL}
    stat = THOUGHTS[name].stat  # the stat this thought is about (declared in @thought)

    if stat and s[stat] >= FULL:
        v.errors.append(f"{stat} is already {s[stat]}; '{name}' makes no sense")
    if critical and stat not in critical:
        crit = ", ".join(f"{k}={val}" for k, val in critical.items())
        v.errors.append(f"critical stats ({crit}) but chose '{name}'")
    if name == "play" and s["energy"] < CRITICAL:
        v.errors.append("energy is too low to play")
    if stat is None and min(s.values()) < 50:
        v.warnings.append(f"chose '{name}' while some stats are low")

    v.ok = not v.errors
    return v


class Supervisor:
    def __init__(self, log_path: str | Path = "logs/supervisor.jsonl"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.total = 0
        self.passed = 0

    def review(self, tick: int, attempt: int, raw: str, state: PetState) -> Verdict:
        verdict = check(raw, state)
        self.total += 1
        self.passed += verdict.ok
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "time": time.time(), "tick": tick, "attempt": attempt,
                "state": state.to_dict(), "raw": raw,
                "ok": verdict.ok, "thought": verdict.thought,
                "errors": verdict.errors, "warnings": verdict.warnings,
            }, ensure_ascii=False) + "\n")
        return verdict

    @property
    def accuracy(self) -> float:
        return self.passed / self.total if self.total else 0.0
