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
├── __init__.py      # Empty package marker
├── __main__.py      # Enables `python -m activityfinder`
├── cli.py           # Click CLI (4 commands: add, search, list, geogrid)
├── geocells.py      # Geohash grid generation via Nominatim (httpx)
├── indexer.py       # In-memory store: index, remove, all, clear
├── models.py        # Activity, SearchCriteria dataclasses
└── recommender.py   # Search/filter against an Indexer instance
```

- **CLI → Recommender → Indexer** — decoupled so the same recommender/indexer can be reused by an API layer later.
- `models.py` has zero dependencies beyond stdlib.
- `recommender.py` depends only on `indexer.py` and `models.py` — no Click dependency.
- `geocells.py` depends on `httpx` (Nominatim geocoding API) but not on Click or other app modules.
- Data is **in-memory per process** (no persistence yet). Each `activityfinder` CLI invocation starts fresh.

## Geocells (src/activityfinder/geocells.py)

Generates a geohash grid for a location via the Nominatim geocoding API (httpx).

- **`Geocell`** dataclass: `geohash`, `latitude`, `longitude`, `precision`
- **`Geogrid`** dataclass: `location`, `latitude`, `longitude`, `cells: list[Geocell]`
- **`GeocellsError`** / **`GeocodeError`** — custom exceptions
- **`generate_geogrid(location, precision, radius_km)`** — main entry point; resolves location via Nominatim, auto-picks precision and radius if omitted, generates deduplicated geohash cells
- **`geocode_location(location) -> (lat, lng)`** — simple lat/lng lookup
- Contains internal geohash encode/decode/step helpers (pure Python, no external geohash library)
- Default max grid cells: 10,000

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

Click group `main` with four commands:

- `add` — index an activity (requires `--title`, `--description`, `--location`; optional `--category`, `--cost`, `--tags`, `--source`, `--url`, `--start-time`)
- `search` — search by `--query`, `--category` (repeatable), `--max-cost`, `--location`, `--tag` (repeatable)
- `list` — list all indexed activities
- `geogrid` — generate a geohash grid for a LOCATION argument (optional `--precision`, `--radius`)

The `list` command is registered as `@main.command(name="list")` with function name `list_activities` to avoid shadowing the built-in.

## Testing

```bash
.venv/bin/pytest -v
```

Tests are in `tests/`. Add test files alongside existing ones following the same class-per-module pattern. CLI tests should use `CliRunner` from `click.testing`.
