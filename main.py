"""Main loop: stats -> (code) thought -> (LLM) action -> (code) update stats -> repeat"""
import argparse
import queue
import sys
import threading
import textwrap
import time

from pet import config
from pet.actions import ACTIONS, apply_action
from pet.interactions import INTERACTIONS, apply_interaction
from pet.memory import Memory
from pet.brain import GeminiBrain, MockBrain, build_prompt, parse
from pet.renderer import TextRenderer
from pet.state import PetState
from pet.thoughts import current_thought

MEMORY_SIZE = 10  # how many previous ticks the LLM is shown


def main() -> None:
    p = argparse.ArgumentParser(description="A text-based pet driven by an LLM")
    p.add_argument("--name", default="Mochi")
    p.add_argument("--ticks", type=int, default=10, help="number of ticks to run (0 = forever)")
    p.add_argument("--auto", type=float, metavar="SECONDS",
                   help="auto mode: run a tick every SECONDS seconds; without it, manual mode (press Enter)")
    p.add_argument("--mock", action="store_true", help="use a fake brain instead of calling the API")
    p.add_argument("--config", default=str(config.DEFAULT_PATH), help="path to the config file")
    p.add_argument("--model", help="override the model in config.toml")
    p.add_argument("--debug", action="store_true",
                   help="debug mode: show the prompt sent to the LLM and its raw output")
    args = p.parse_args()

    cfg = config.load(args.config)
    if args.model:
        cfg.gemini.model = args.model

    state = PetState()
    brain = MockBrain() if args.mock else GeminiBrain(cfg.gemini)
    ui = TextRenderer(args.debug)

    if args.auto is not None and args.auto <= 0:
        p.error("--auto must be greater than 0")

    print(f"=== {args.name} is born! ===")
    if args.debug:
        models = "mock" if args.mock else f"model={cfg.gemini.model}, fallbacks={cfg.gemini.fallback_models}"
        print(f"(debug mode: {models})")
    if args.auto:
        print(f"(auto mode: a tick every {args.auto:g}s)")
    else:
        print("(manual mode: press Enter for the next tick)")
    ui.show_state(state, {})

    tick = 0
    memory = Memory(MEMORY_SIZE, cfg.memory)
    next_time = time.monotonic()

    # Input area: a background thread reads the lines the owner types
    typed: queue.Queue[str | None] = queue.Queue()  # None = stdin closed

    def read_input() -> None:
        for line in sys.stdin:
            typed.put(line.strip().lower())
        typed.put(None)

    threading.Thread(target=read_input, daemon=True).start()

    def handle(cmd: str) -> None:
        """Apply an owner interaction typed in the input area."""
        item = INTERACTIONS.get(cmd)
        if item is None:
            if cmd:
                print(f"   (unknown input: {cmd!r})")
            return
        before = current_thought(state)
        delta = apply_interaction(state, item)
        memory.add(f"owner_{item.name}", f"{before}>{current_thought(state)}")
        ui.show_interaction(args.name, item, delta)

    def wait_for_tick() -> bool:
        """Wait until the next tick is due, handling input meanwhile. False = quit."""
        nonlocal next_time
        stdin_open = True
        while True:
            if args.auto:
                remaining = next_time - time.monotonic()
                if remaining <= 0:
                    break
            else:
                remaining = None  # manual mode: wait for Enter
            if not stdin_open:
                if not args.auto:
                    return False
                time.sleep(remaining)
                break
            ui.show_input_area(INTERACTIONS.values(), manual=not args.auto)
            try:
                cmd = typed.get(timeout=remaining)
            except queue.Empty:
                break
            if cmd is None:
                stdin_open = False
            elif cmd == "q":
                return False
            elif cmd == "" and not args.auto:
                break  # Enter: next tick
            else:
                handle(cmd)
        if args.auto:
            next_time = max(next_time, time.monotonic() - args.auto) + args.auto
        return True

    try:
        while args.ticks == 0 or tick < args.ticks:
            started_waiting = time.monotonic()
            if not wait_for_tick():
                break
            # In auto mode, a tick that starts without any wait means the last one ran over
            late = bool(args.auto) and tick > 0 and time.monotonic() - started_waiting < 0.001

            tick += 1
            ui.begin_tick(tick)  # normal mode clears the screen here
            if late:
                print(f"   ⏱️  the last tick took longer than {args.auto:g}s, running now")

            # 1. Stats -> the one most urgent thought (code)
            thought = current_thought(state)
            ui.show_thought(thought)

            recalled = memory.recall()
            if args.debug:
                print("   [debug] prompt sent to the LLM:")
                print(textwrap.indent(build_prompt(thought, recalled), "      "))

            # 2. Thought + memory -> action (LLM); no usable reply -> no action this tick
            try:
                raw = brain.decide(thought, recalled)
            except Exception as e:  # API errors (network, key, quota, ...) shouldn't crash the program
                print(f"   [LLM error] {type(e).__name__}: {str(e)[:150]}")
                raw = ""
            ui.show_debug(getattr(brain, "last_model", None), raw)
            action_name = parse(raw)

            # 3. Action -> stats (code)
            result = apply_action(state, action_name)

            # 4. Remember how the action changed the pet's thought, and display
            if action_name:
                label = action_name if result.applied else f"{action_name} (no effect)"
                memory.add(label, f"{thought}>{current_thought(state)}")
                ui.show_action(args.name, ACTIONS[action_name], result.applied)
            else:
                ui.show_no_action(args.name, raw)
            ui.show_state(state, result.delta)

            if state.health == 0:
                print(f"\n💀 {args.name} has fallen ill...")
                break
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
