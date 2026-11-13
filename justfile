# List all recipes
default:
    @just --list

# Install / sync dependencies
sync:
    uv sync

# Create config.toml from the template (won't overwrite an existing one)
init:
    @[ -f config.toml ] && echo "config.toml already exists" || (cp config.example.toml config.toml && echo "Created config.toml; fill in api_key")

# Manual mode (press Enter for each tick); extra args allowed, e.g. just run --ticks 0
run *args:
    uv run main.py {{args}}

# Auto mode: a tick every N seconds, forever (default 5s)
auto seconds="5" *args:
    uv run main.py --auto {{seconds}} --ticks 0 {{args}}

# Test with a fake brain, no API calls (auto mode, default 1s)
mock seconds="1" *args:
    uv run main.py --mock --auto {{seconds}} {{args}}

# Show the last N supervisor log entries
log n="20":
    tail -n {{n}} logs/supervisor.jsonl

# Delete the supervisor log
clean-log:
    rm -rf logs
