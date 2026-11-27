# List all recipes
default:
    @just --list

# Install / sync dependencies
sync:
    uv sync

# Create config.toml from the template (won't overwrite an existing one)
init:
    @[ -f config.toml ] && echo "config.toml already exists" || (cp config.example.toml config.toml && echo "Created config.toml; fill in api_key")

# Web UI at http://localhost:<port> (listens on 0.0.0.0), default port 8000; e.g. just web 9000 --mock
web port="8000" *args:
    uv run -m webui --port {{port}} {{args}}

# Web UI in the background (restarts it if it's already running); output in .server.log; e.g. just start 9000 --mock
start port="8000" *args: stop
    #!/usr/bin/env bash
    set -euo pipefail
    # setsid: its own process group, so `just stop` ends uv and the python under it together
    setsid nohup uv run -m webui --port {{port}} {{args}} > .server.log 2>&1 < /dev/null &
    echo $! > .server.pid
    sleep 1
    if kill -0 "$(cat .server.pid)" 2>/dev/null; then
        echo "server running on http://localhost:{{port}} (pid $(cat .server.pid)); log: .server.log; stop: just stop"
    else
        echo "server didn't start; .server.log says:"; tail -n 20 .server.log; rm -f .server.pid; exit 1
    fi

# Stop the background web UI started by `just start`
stop:
    #!/usr/bin/env bash
    if [ -f .server.pid ]; then
        pid=$(cat .server.pid)
        if kill -0 "$pid" 2>/dev/null; then
            kill -- "-$pid" 2>/dev/null || kill "$pid"
            for _ in $(seq 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
            echo "stopped the server (pid $pid)"
        fi
        rm -f .server.pid
    fi

# Web UI in debug mode: the log also shows the prompts and the model's raw replies
debug port="8000" *args:
    uv run -m webui --port {{port}} --debug {{args}}

# Web UI with a fake brain (random actions), no model calls
mock port="8000" *args:
    uv run -m webui --port {{port}} --mock {{args}}

# Cut design.png (five poses without eyes + a column of eyes) into the pet's still images; e.g. just sprites --preview check.png
sprites *args:
    uv run --with pillow --with numpy --with scipy python -m webui.slice_poses design.png {{args}}
