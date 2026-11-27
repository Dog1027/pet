"""The simulation: the pet does one action at a time, in real time.

    pick an action -> it runs for its duration, changing the stats and the world -> pick the next

A host (the web UI) creates an Engine and calls step() about once a second. Each step:
  - runs the current action for the real seconds since the last step (actions.py: the action's
    function makes the world changes and returns the stat changes)
  - once the action's duration is over, or its stop_when says so, stores it in memory and
    picks the next one, trying in order:
        1. the finished action's `then` (actions.py)
        2. a reflex: a stat that is too low picks a set action (reflexes.py)
        3. the LLM, from the pet's thought and memory
  - the LLM is asked in a background thread. While it thinks (or waits to ask again after a
    bad reply) no action runs, but the pet still lives: it pays the cost of living
    (actions.living: hunger, tiredness, loneliness, health lost to neglect) and can fall ill
Owner interactions (interact()) take effect at once, whatever the pet is doing. An interaction
with an action (e.g. cuddle -> "cuddled") interrupts the running action, which ends there without
running `then`, and the pet starts the interaction's action.

Everything that changes the pet happens under self.lock, so the host may call step(),
interact() and snapshot() from different threads.
"""
import threading
import time
from dataclasses import dataclass

from .actions import ACTIONS, Action, Step, living
from .brain import Brain, build_prompt, parse
from .config import Config
from .interactions import INTERACTIONS, apply_interaction
from .memory import Memory
from .reflexes import reflex_action
from .renderer import Renderer
from .state import PetState
from .thoughts import current_thought
from .world import World, diff

MEMORY_SIZE = 10        # how many previous actions the LLM is shown
RETRY_SECONDS = 3.0     # after an unusable reply / error, wait this long before asking again
MAX_STEP_SECONDS = 5.0  # a longer gap between steps (e.g. the computer slept) counts as this much


@dataclass
class Running:
    """The action the pet is doing right now."""
    action: Action
    thought: str          # the pet's thought when it started
    chosen_by: str        # who picked it: the action whose `then` did, "reflex: ...", "llm",
                          # or "owner_<interaction>"
    before: dict = None   # the stats when it started (for the action's result)
    owner: list = None    # owner interactions while it ran ("feed", "cuddle")
    elapsed: float = 0.0  # seconds done so far

    @property
    def remaining(self) -> float:
        return max(self.action.duration - self.elapsed, 0.0)


class Engine:
    def __init__(self, name: str, cfg: Config, brain: Brain, ui: Renderer):
        for item in INTERACTIONS.values():
            if item.action is not None and item.action not in ACTIONS:
                raise ValueError(f"interaction {item.name}: {item.action!r} is not an action")
        self.name = name
        self.brain = brain
        self.ui = ui
        self.state = PetState()
        self.world = World()
        self.memory = Memory(MEMORY_SIZE, cfg.memory, cfg.gemini)
        self.lock = threading.RLock()
        self.alive = True
        self.age = 0.0                           # seconds the pet has lived
        self.running: Running | None = None
        self.thinking = False                    # a brain call is in progress
        self.next_decision_at = 0.0              # age at which the pet may ask the LLM again
        self.last_chosen_by: str | None = None   # who picked the action that ended last
        self.rates: dict[str, float] = {}        # change per second during the last step
        self._last_step: float | None = None     # time.monotonic() of the last step

    # ------------------------------------------------------------ time

    def step(self) -> None:
        """Advance the simulation to now. Call about once a second."""
        now = time.monotonic()
        with self.lock:
            dt = 0.0 if self._last_step is None else min(now - self._last_step, MAX_STEP_SECONDS)
            self._last_step = now
            if not self.alive:
                return
            self.age += dt
            if self.running is not None and dt > 0:
                self._run(dt)
            elif self.running is None and dt > 0:
                self._wait(dt)
            if self.alive and self.running is None and not self.thinking:
                self._pick_without_then()

    def _pick_without_then(self) -> None:
        """No action is running and no `then` picked one: a reflex, or else the LLM.
        A reflex doesn't fire twice in a row: after it, the LLM gets the next pick, so a reflex
        that didn't help (scavenge with no food anywhere) can't keep the pet from trying
        something else."""
        reflex = reflex_action(self.state)
        by = reflex and f"reflex: {reflex[1].stat} < {reflex[1].below:g}"
        if reflex is not None and by != self.last_chosen_by:
            self._start(reflex[0], chosen_by=by)
        elif self.age >= self.next_decision_at:
            self._start_thinking()

    def _wait(self, dt: float) -> None:
        """No action running (thinking, or waiting to ask again): the cost of living still applies."""
        before = self.state.to_dict()
        self.state.apply(living(self.state, Step(0.0, dt, dt)))
        self.rates = {k: v / dt for k, v in diff(before, self.state.to_dict()).items()}
        self._check_ill()

    def _check_ill(self) -> bool:
        """Fall ill if health is gone. True if the pet just fell ill."""
        if self.state.health > 0:
            return False
        self.alive = False
        self.running = None
        self.ui.show_note(f"💀 {self.name} has fallen ill...")
        return True

    def _run(self, dt: float) -> None:
        """Run the current action for dt seconds (or what is left of it)."""
        r = self.running
        end = r.action.duration if dt >= r.remaining else r.elapsed + dt  # exact at the last step
        step = Step(r.elapsed, end, r.action.duration)
        seconds = step.seconds
        before = self.state.to_dict()
        self.state.apply(r.action.fn(self.state, self.world, step))
        r.elapsed = step.end
        self.rates = {k: v / seconds for k, v in diff(before, self.state.to_dict()).items()}

        if self._check_ill():
            pass
        elif r.remaining == 0 or r.action.should_stop(self.state, self.world):
            self._finish()
            nxt = r.action.next_action(self.state, self.world)
            if nxt is not None:
                self._start(nxt, chosen_by=r.action.name)
            else:
                self.next_decision_at = self.age  # no waiting for the LLM
                self._pick_without_then()

    def _finish(self, interrupted: bool = False, thought_after: str | None = None) -> None:
        r = self.running
        self.running = None
        self.last_chosen_by = r.chosen_by
        label = r.action.name + (" (interrupted)" if interrupted else "")
        if r.action.result is not None:  # what came of it: "scavenge: found nothing"
            label += f": {r.action.result(r.before, self.state, self.world, r.owner)}"
        self.memory.add(label, f"{r.thought}>{thought_after or current_thought(self.state)}")
        self.ui.show_action_done(self.name, r.action, interrupted)

    def _start(self, action: Action, chosen_by: str) -> None:
        self.running = Running(action, current_thought(self.state), chosen_by,
                               before=self.state.to_dict(), owner=[])
        self.ui.show_action(self.name, action, chosen_by)

    # ------------------------------------------------------------ the LLM

    def _start_thinking(self) -> None:
        self.thinking = True
        thought = current_thought(self.state)
        self.ui.show_thought(thought)
        threading.Thread(target=self._think, args=(thought,), daemon=True).start()

    def _think(self, thought: str) -> None:
        """Background thread: ask the LLM, then start the action it picked."""
        recalled = self.memory.recall()
        prompt = build_prompt(thought, recalled)
        self.ui.show_prompt(prompt)
        try:
            raw = self.brain.decide(prompt)
            error = None
        except Exception as e:  # API errors (network, key, quota, ...) shouldn't stop the pet
            raw, error = "", e
        with self.lock:
            self.thinking = False
            if error is not None:
                self.ui.show_note(f"[LLM error] {type(error).__name__}: {str(error)[:150]}")
            self.ui.show_debug(getattr(self.brain, "last_model", None), raw)
            if not self.alive or self.running is not None:
                return  # ill, or an interaction started an action while the LLM was thinking
            name = parse(raw)
            if name is None:
                if error is None:
                    self.ui.show_no_action(self.name, raw)
                self.next_decision_at = self.age + RETRY_SECONDS
                return
            self._start(ACTIONS[name], chosen_by="llm")

    # ------------------------------------------------------------ the owner

    def interact(self, key: str, **options) -> bool:
        """Run the owner interaction bound to key, with the options it takes (e.g. feed: x, y).
        False if there is none or the pet is ill; raises TypeError / ValueError for bad options."""
        item = INTERACTIONS.get(key)
        if item is None or not self.alive:
            return False
        with self.lock:
            before = current_thought(self.state)
            delta = apply_interaction(self.state, self.world, item, **options)  # may raise: nothing changed
            if self.running is not None:
                self.running.owner.append(item.name)  # for the running action's result
            if item.action is not None and self.running is not None:
                self._finish(interrupted=True, thought_after=before)  # how it was when interrupted
            self.memory.add(f"owner_{item.name}", f"{before}>{current_thought(self.state)}")
            self.ui.show_interaction(self.name, item, delta)
            self.ui.show_state(self.state, self.world, delta)
            if item.action is not None:
                self._start(ACTIONS[item.action], chosen_by=f"owner_{item.name}")
        return True

    # ------------------------------------------------------------ reading

    def snapshot(self) -> dict:
        """Everything a display needs, as plain data."""
        with self.lock:
            r = self.running
            thought = current_thought(self.state)
            return {
                "name": self.name,
                "alive": self.alive,
                "age": self.age,
                "thought": thought,
                "thinking": self.thinking,
                "action": None if r is None else {
                    "name": r.action.name,
                    "label": r.action.label,
                    "chosen_by": r.chosen_by,
                    "duration": r.action.duration,
                    "elapsed": r.elapsed,
                },
                # Everything the pet's picture depends on
                "look": {
                    "pose": r.action.pose if r else "stand",
                    "prop": r.action.prop if r else None,
                    "action": r.action.name if r else None,
                    "expression": thought,
                    "alive": self.alive,
                },
                "stats": self.state.to_dict(),
                "rates": dict(self.rates),
                "world": self.world.to_dict(),
                "interactions": [{"name": i.name, "key": i.key, "label": i.label} for i in INTERACTIONS.values()],
            }
