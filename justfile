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

# Web UI in debug mode: the log also shows the prompts and the model's raw replies
debug port="8000" *args:
    uv run -m webui --port {{port}} --debug {{args}}

# Web UI with a fake brain (random actions), no model calls
mock port="8000" *args:
    uv run -m webui --port {{port}} --mock {{args}}

# Cut design.png (five poses without eyes + a column of eyes) into the pet's still images; e.g. just sprites --preview check.png
sprites *args:
    uv run --with pillow --with numpy --with scipy python -m webui.slice_poses design.png {{args}}
