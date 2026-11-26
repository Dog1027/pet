"""Web UI: runs the pet (pet/engine.py) and serves it to a browser.

The core doesn't know about the web: this module plugs in through the Renderer interface
(WebRenderer collects the events for the page) and reads Engine.snapshot().

    uv run -m webui              # then open http://localhost:8000 (or this machine's IP from another device)

HTTP API (JSON):
    GET  /api/state         everything the page shows (Engine.snapshot() + the log)
    GET  /api/sprites       the pet's PNG sprites found in static/sprites/ (see sprites.py)
    POST /api/interact      {"key": "c"}  -> run an owner interaction
                            {"key": "f", "x": 3, "y": 4}  -> feed: put food at (3, 4)
Files under webui/static/ are served at /. The pet's PNGs go in webui/static/sprites/
(naming: sprites.py); until they're there, static/pet-view.js draws the pet itself.
"""
import argparse
import json
import threading
import time
from collections import deque
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pet import config
from pet.brain import build_prompt, make_brain
from pet.engine import Engine
from pet.forgetting import METHODS as FORGETTING_METHODS
from pet.renderer import Renderer, changes

from . import sprites

STATIC_DIR = Path(__file__).resolve().parent / "static"
STEP_SECONDS = 1.0  # how often time advances
LOG_SIZE = 50       # events kept for the page


class WebRenderer(Renderer):
    """Keeps the recent events for the page's log."""

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.log: deque[dict] = deque(maxlen=LOG_SIZE)
        self.lock = threading.Lock()

    def _add(self, kind: str, text: str) -> None:
        with self.lock:
            self.log.append({"kind": kind, "text": text, "at": time.time()})

    def entries(self) -> list[dict]:
        with self.lock:
            return list(self.log)

    def show_thought(self, thought):
        self._add("thought", f"thought: {thought} ... thinking")

    def show_prompt(self, thought, memory):
        if self.debug:
            self._add("debug", "prompt: " + build_prompt(thought, memory).replace("\n", " / "))

    def show_debug(self, model, raw):
        if self.debug:
            self._add("debug", f"model={model} raw={raw.strip()!r}")

    def show_action(self, pet_name, action, chosen_by):
        by = {"llm": "decides"}.get(chosen_by, f"({chosen_by})")
        self._add("action", f"{pet_name} {by}: [{action.label}] up to {action.duration:g}s")

    def show_no_action(self, pet_name, raw):
        self._add("action", f"{pet_name} does nothing (unusable reply: {raw.strip()!r})")

    def show_action_done(self, pet_name, action, interrupted=False):
        if interrupted:
            self._add("action", f"{pet_name} stops [{action.label}]")

    def show_interaction(self, pet_name, item, delta):
        self._add("interaction", f"You [{item.label}] {pet_name}: {changes(delta)}")

    def show_note(self, text):
        self._add("note", text)


def run_clock(engine: Engine) -> None:
    """Background thread: advance time once a second."""
    next_step = time.monotonic()
    while engine.alive:
        engine.step()
        next_step += STEP_SECONDS
        time.sleep(max(next_step - time.monotonic(), 0))
        next_step = max(next_step, time.monotonic())  # a slow step doesn't cause a burst


def make_handler(engine: Engine, ui: WebRenderer):
    def state() -> dict:
        return {**engine.snapshot(), "log": ui.entries()}

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

        def log_message(self, fmt, *args):  # keep the terminal quiet
            pass

        def end_headers(self):
            # Static files: make the browser check for a newer version every time,
            # so edits to the page show on a normal reload (the API sets its own no-store)
            if not self.path.startswith("/api/"):
                self.send_header("Cache-Control", "no-cache")
            super().end_headers()

        def _json(self, data, status=HTTPStatus.OK):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/api/state":
                self._json(state())
            elif self.path == "/api/sprites":
                self._json(sprites.describe())  # re-scanned each time: new files show on reload
            else:
                super().do_GET()

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._json({"error": "invalid JSON"}, HTTPStatus.BAD_REQUEST)
            if self.path != "/api/interact":
                return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            options = {k: body[k] for k in ("x", "y") if k in body}  # feed: where to put the food
            try:
                ok = engine.interact(str(body.get("key", "")), **options)
            except (TypeError, ValueError) as e:
                return self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
            if not ok:
                return self._json({"error": "unknown interaction"}, HTTPStatus.BAD_REQUEST)
            self._json(state())

    return Handler


def main() -> None:
    p = argparse.ArgumentParser(description="Web UI for the pet")
    p.add_argument("--name", default="Mochi")
    p.add_argument("--mock", action="store_true", help="use a fake brain instead of calling the API")
    p.add_argument("--config", default=str(config.DEFAULT_PATH), help="path to the config file")
    p.add_argument("--forgetting", choices=sorted(FORGETTING_METHODS),
                   help="override the forgetting method in config.toml")
    p.add_argument("--debug", action="store_true", help="also show the prompts sent to the model and its raw replies in the log")
    p.add_argument("--host", default="0.0.0.0",
                   help="address to listen on (default 0.0.0.0: reachable from other devices; 127.0.0.1 = this machine only)")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()

    cfg = config.load(args.config)
    if args.forgetting:
        cfg.memory.forgetting = args.forgetting
    try:
        brain = make_brain(cfg, args.mock)
    except ValueError as e:
        p.error(str(e))

    ui = WebRenderer(args.debug)
    engine = Engine(args.name, cfg, brain, ui)
    threading.Thread(target=run_clock, args=(engine,), daemon=True).start()

    server = ThreadingHTTPServer((args.host, args.port), make_handler(engine, ui))
    shown = "localhost" if args.host in ("0.0.0.0", "::") else args.host
    print(f"{args.name} is at http://{shown}:{args.port}  "
          f"(brain={'mock' if args.mock else cfg.brain}; Ctrl+C to quit)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
