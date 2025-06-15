[private]
default:
    @just --list

# Run the project's lint checks
lint:
    uv run ruff check src
    uv run mypy src tests

# Run the project's formatter and other automatically fixable issues
autofix:
    uv run ruff check --fix
    uv run ruff format src

# Run the project tests
test *args:
    uv run pytest tests {{args}}
