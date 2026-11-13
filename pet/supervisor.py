"""Supervise whether the LLM's output is correct.

Three levels of checks:
1. Format: is it valid JSON with the required fields?
2. Validity: does the action exist in the action table?
3. Sanity: does the action make sense for the current stats? (rule-based)

Every verdict is written to a JSONL log so the LLM's accuracy can be analysed later.
"""
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from .actions import ACTIONS
from .state import PetState

FULL = 90          # a stat >= this counts as "already full"
CRITICAL = 20      # a stat < this counts as "critical"


@dataclass
class Verdict:
    ok: bool
    action: str | None = None
    reason: str = ""            # reason given by the LLM
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def feedback(self) -> str:
        return "; ".join(self.errors)


def _extract_json(raw: str) -> dict | None:
    raw = raw.strip()
    # tolerate a ```json ... ``` wrapper
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def check(raw: str, state: PetState, expect_reason: bool = False) -> Verdict:
    # 1. Format
    obj = _extract_json(raw)
    if obj is None:
        return Verdict(False, errors=["output is not a valid JSON object"])
    action = obj.get("action")
    reason = obj.get("reason", "")
    if not isinstance(action, str):
        return Verdict(False, errors=["missing string field 'action'"])

    # 2. Validity
    if action not in ACTIONS:
        return Verdict(False, action, reason,
                       errors=[f"action '{action}' does not exist; available: {', '.join(ACTIONS)}"])

    v = Verdict(True, action, reason)
    s = state.to_dict()

    # 3. Sanity
    critical = {k: val for k, val in s.items() if val < CRITICAL}
    primary = ACTIONS[action].restores  # main stat the action restores (declared in @action)

    if primary and s[primary] >= FULL:
        v.errors.append(f"{primary} is already {s[primary]}; no need to {action}")
    if critical and primary not in critical:
        crit = ", ".join(f"{k}={val}" for k, val in critical.items())
        v.errors.append(f"critical stats ({crit}) but chose {action}")
    if action == "play" and s["energy"] < CRITICAL:
        v.errors.append("energy is too low to play")
    if action == "idle" and min(s.values()) < 50:
        v.warnings.append("chose to idle while some stats are low")
    if expect_reason and not reason:  # reasons are only requested in debug mode
        v.warnings.append("no reason given")

    v.ok = not v.errors
    return v


class Supervisor:
    def __init__(self, log_path: str | Path = "logs/supervisor.jsonl", debug: bool = False):
        self.debug = debug
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.total = 0
        self.passed = 0

    def review(self, tick: int, attempt: int, raw: str, state: PetState) -> Verdict:
        verdict = check(raw, state, expect_reason=self.debug)
        self.total += 1
        self.passed += verdict.ok
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "time": time.time(), "tick": tick, "attempt": attempt,
                "state": state.to_dict(), "raw": raw,
                "ok": verdict.ok, "action": verdict.action,
                "errors": verdict.errors, "warnings": verdict.warnings,
            }, ensure_ascii=False) + "\n")
        return verdict

    @property
    def accuracy(self) -> float:
        return self.passed / self.total if self.total else 0.0
