"""Main loop: stats -> (LLM) thought -> (supervisor) -> (decision tree) action -> (code) update stats -> repeat"""
import argparse
import time
from collections import deque

from pet import config
from pet.actions import ACTIONS, apply_action
from pet.brain import GeminiBrain, MockBrain
from pet.renderer import TextRenderer
from pet.state import PetState
from pet.supervisor import Supervisor
from pet.thoughts import resolve, safe_thought

MEMORY_SIZE = 3  # how many previous actions the LLM is shown


def main() -> None:
    p = argparse.ArgumentParser(description="A text-based pet driven by an LLM")
    p.add_argument("--name", default="Mochi")
    p.add_argument("--ticks", type=int, default=10, help="number of ticks to run (0 = forever)")
    p.add_argument("--auto", type=float, metavar="SECONDS",
                   help="auto mode: run a tick every SECONDS seconds; without it, manual mode (press Enter)")
    p.add_argument("--retries", type=int, default=2, help="retries when the LLM's output is rejected")
    p.add_argument("--mock", action="store_true", help="use a fake brain instead of calling the API")
    p.add_argument("--config", default=str(config.DEFAULT_PATH), help="path to the config file")
    p.add_argument("--model", help="override the model in config.toml")
    p.add_argument("--debug", action="store_true",
                   help="debug mode: show the LLM's raw output and the thought -> action step")
    args = p.parse_args()

    cfg = config.load(args.config)
    if args.model:
        cfg.model = args.model

    state = PetState()
    brain = MockBrain() if args.mock else GeminiBrain(cfg)
    supervisor = Supervisor()
    ui = TextRenderer(args.debug)

    if args.auto is not None and args.auto <= 0:
        p.error("--auto must be greater than 0")

    print(f"=== {args.name} is born! ===")
    if args.debug:
        models = "mock" if args.mock else f"model={cfg.model}, fallbacks={cfg.fallback_models}"
        print(f"(debug mode: {models})")
    if args.auto:
        print(f"(auto mode: a tick every {args.auto:g}s, Ctrl+C to quit)")
    else:
        print("(manual mode: press Enter for the next tick, type q to quit)")
    ui.show_state(state, {})

    tick = 0
    memory: deque[str] = deque(maxlen=MEMORY_SIZE)  # recent actions, oldest first
    next_time = time.monotonic()
    try:
        while args.ticks == 0 or tick < args.ticks:
            late = False
            if args.auto:
                # Fixed rate: measured from the *start* of the previous tick, so LLM time is included
                wait = next_time - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                elif tick > 0:
                    late = True
                next_time = max(next_time, time.monotonic() - args.auto) + args.auto
            else:
                try:
                    if input("\n[Enter] next tick / q to quit > ").strip().lower() == "q":
                        break
                except EOFError:
                    break

            tick += 1
            ui.begin_tick(tick)  # normal mode clears the screen here
            if late:
                print(f"   ⏱️  the last tick took longer than {args.auto:g}s, running now")

            if args.debug:
                print(f"   [debug] memory sent to the LLM: {list(memory)}")

            # 1. Stats -> thought (LLM), checked by the supervisor; if rejected, ask again with feedback
            feedback, verdict = None, None
            for attempt in range(1, args.retries + 2):
                try:
                    raw = brain.decide(state, feedback, memory)
                except Exception as e:  # API errors (network, key, quota, ...) shouldn't crash the program
                    print(f"   [LLM error] {type(e).__name__}: {str(e)[:150]}")
                    raw = ""  # the supervisor rejects it; retry or fall back as usual
                ui.show_debug(attempt, getattr(brain, "last_model", None), raw)
                verdict = supervisor.review(tick, attempt, raw, state)
                ui.show_supervisor(attempt, verdict.ok, verdict.errors, verdict.warnings)
                if verdict.ok:
                    break
                feedback = verdict.feedback()

            if verdict.ok:
                thought_name, used_fallback = verdict.thought, False
            else:
                # The LLM kept getting it wrong: use the thought about the lowest stat
                thought_name, used_fallback = safe_thought(state), True

            # 2. Thought -> action (decision tree, code)
            action_name = resolve(thought_name, state)

            # 3. Action -> stats (code)
            result = apply_action(state, action_name)
            memory.append(action_name if result.applied else f"{action_name} (no effect)")

            # 4. Display
            ui.show_action(args.name, ACTIONS[action_name], thought_name, used_fallback, result.applied)
            ui.show_state(state, result.delta)

            if state.health == 0:
                print(f"\n💀 {args.name} has fallen ill...")
                break
    except KeyboardInterrupt:
        pass

    print(f"\n=== Supervisor stats: LLM pass rate {supervisor.accuracy:.0%}"
          f" ({supervisor.passed}/{supervisor.total}), details in {supervisor.log_path} ===")


if __name__ == "__main__":
    main()
