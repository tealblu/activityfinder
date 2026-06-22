# Activity Finder

Index local things to do ("activities") and recommend them based on search criteria. Currently CLI-only; will expose an API + UI later.

## Quick start

```bash
.venv/bin/pip install -e .
.venv/bin/pytest          # 12 tests, all pass
.venv/bin/activityfinder --help
```

> **IMPORTANT: Keep this file up to date.** Whenever you add, remove, rename, or refactor a module, change a dependency, alter the CLI interface, or modify the project structure in any way, update this file to reflect it. Add new sections for new subsystems (e.g., API, database). This file is the single source of truth for project context — stale entries here mislead future agents.

## Architecture

```
src/activityfinder/
├── models.py        # Activity, SearchCriteria dataclasses
├── indexer.py       # In-memory store: index, remove, all, clear
├── recommender.py   # Search/filter against an Indexer instance
├── cli.py           # Click CLI (3 commands: add, search, list)
├── geocells.py      # Geohash grid ingestion pipeline
└── __main__.py      # Enables `python -m activityfinder`
```

- **CLI → Recommender → Indexer** — decoupled so the same recommender/indexer can be reused by an API layer later.
- `models.py` has zero dependencies beyond stdlib.
- `recommender.py` depends only on `indexer.py` and `models.py` — no Click dependency.
- Data is **in-memory per process** (no persistence yet). Each `activityfinder` CLI invocation starts fresh.

## Conventions

- Python 3.10+ with full type annotations.
- `pyproject.toml`-based project (no `setup.py`).
- `src/` layout.
- Tests use `pytest` with class-based organization (`Test*` classes, `setup_method`).
- CLI tests use `click.testing.CliRunner`.
- Do not add comments to code unless asked.
- Do not create documentation files (`*.md`) unless explicitly requested.

## Key models (src/activityfinder/models.py)

**`ActivityCategory`** — str Enum: sports, arts, music, food, outdoors, education, social, entertainment, other.

**`Activity`** dataclass:
- `title`, `description`, `category`, `location` (required)
- `start_time` (defaults to now), `end_time` (optional)
- `cost` (float, default 0.0), `tags` (list[str]), `source`, `url`

**`SearchCriteria`** dataclass:
- `query`, `categories`, `max_cost`, `location`, `tags` — all optional

## Indexer (src/activityfinder/indexer.py)

Simple in-memory list-based store:
- `index(activity)`, `index_many(activities)`, `remove(title) -> bool`, `all() -> list[Activity]`, `clear()`

## Recommender (src/activityfinder/recommender.py)

Filter-based search; applies each non-empty criterion as a narrowing filter:
1. query → substring match on title/description (case-insensitive)
2. categories → exact match
3. max_cost → `cost <= max_cost`
4. location → substring match (case-insensitive)
5. tags → any overlap

## CLI (src/activityfinder/cli.py)

Click group `main` with three commands:

- `add` — index an activity (requires `--title`, `--description`, `--location`; optional `--category`, `--cost`, `--tags`, `--source`, `--url`, `--start-time`)
- `search` — search by `--query`, `--category` (repeatable), `--max-cost`, `--location`, `--tag` (repeatable)
- `list` — list all indexed activities

The `list` command is registered as `@main.command(name="list")` with function name `list_activities` to avoid shadowing the built-in.

## Testing

```bash
.venv/bin/pytest -v
```

Tests are in `tests/`. Add test files alongside existing ones following the same class-per-module pattern. CLI tests should use `CliRunner` from `click.testing`.
