# Activity Finder

Index local things to do ("activities") and recommend them based on search criteria. Currently CLI-only; will expose an API + UI later.

## Quick start

```bash
.venv/bin/pip install -e .
.venv/bin/pytest          # 39 tests, all pass
.venv/bin/activityfinder --help
```

> **IMPORTANT: Keep this file up to date.** Whenever you add, remove, rename, or refactor a module, change a dependency, alter the CLI interface, or modify the project structure in any way, update this file to reflect it. Add new sections for new subsystems (e.g., API, database). This file is the single source of truth for project context — stale entries here mislead future agents.

## Architecture

```
src/activityfinder/
├── __init__.py      # Empty package marker
├── __main__.py      # Enables `python -m activityfinder`
├── cli.py           # Typer CLI (4 commands: add, search, list, geogrid; --db option)
├── db.py            # SQLite persistence layer (activities, reviews, cells_fetched, sources)
├── geocells.py      # Geohash grid generation via Nominatim (httpx)
├── indexer.py       # In-memory cache backed by a Database instance
├── models.py        # Activity, SearchCriteria dataclasses
└── recommender.py   # Search/filter against an Indexer instance
```

- **CLI → Recommender → Indexer** — decoupled so the same recommender/indexer can be reused by an API layer later.
- `models.py` has zero dependencies beyond stdlib.
- `recommender.py` depends only on `indexer.py` and `models.py` — no Click dependency.
- `geocells.py` depends on `httpx` (Nominatim geocoding API) but not on Click or other app modules.
- `db.py` depends on `models.py` and stdlib `sqlite3` / `json` — no third-party dependencies.
- Data persists across invocations (SQLite file, default: `activityfinder.db`).

## Geocells (src/activityfinder/geocells.py)

Generates a geohash grid for a location via the Nominatim geocoding API (httpx).

- **`Geocell`** dataclass: `geohash`, `latitude`, `longitude`, `precision`
- **`Geogrid`** dataclass: `location`, `latitude`, `longitude`, `cells: list[Geocell]`
- **`GeocellsError`** / **`GeocodeError`** — custom exceptions
- **`generate_geogrid(location, precision, radius_km)`** — main entry point; resolves location via Nominatim, auto-picks precision and radius if omitted, generates deduplicated geohash cells
- **`geocode_location(location) -> (lat, lng)`** — simple lat/lng lookup
- **`resolve_area(query) -> dict`** — low-level Nominatim lookup returning bounding box, lat/lng, display name, and type
- **`find_cell(cells, latitude, longitude) -> Geocell | None`** — match a lat/lng to a cell in an existing grid via geohash encoding
- Contains internal geohash encode/decode/step helpers (pure Python, no external geohash library)
- Default max grid cells: 10,000

## Database (src/activityfinder/db.py)

SQLite persistence layer accessed via `Database`:

- **`activities`** table — geohash-indexed with lat/lng, category, tags (JSON), cost, times, and `expires_at` for cache-aware expiry
- **`reviews`** table — linked to activities by `activity_id`, with raw text and optional rating for NLP use
- **`cells_fetched`** table — tracks which geohash+source combinations have been crawled so APIs aren't re-hit unnecessarily
- **`sources`** table — each source has a `refresh_cadence_seconds` so cache invalidation is source-aware rather than a single global TTL

Source methods:
- **`get_or_create_source(name, refresh_cadence_seconds=86400) -> int`** — upsert a source, returns its id
- **`get_source(name) -> dict | None`** — lookup a source by name
- **`list_sources() -> list[dict]`** — all sources sorted by name

Activity methods:
- **`add_activity(activity, ...) -> int`** — persist an Activity with optional lat/lng/geohash
- **`remove_activity(title) -> bool`** — delete by title
- **`get_activity_by_title(title) -> Activity | None`**
- **`get_activity_by_id(id) -> dict | None`** — raw row lookup
- **`all_activities() -> list[Activity]`** — all activities, newest first
- **`search_activities(query, category, max_cost, location, tag)`** — filter-based SQL search
- **`clear_activities()`** — delete all

Review methods:
- **`add_review(activity_id, text, rating, author, source_name) -> int`**
- **`get_reviews(activity_id) -> list[dict]`**

Cell cache:
- **`is_cell_fetched(geohash, source) -> bool`**
- **`mark_cell_fetched(geohash, source)`** — record a fetch timestamp
- **`get_stale_cells(source, max_age_seconds=None)`** — returns cells that exceed their source's refresh cadence (or a manual max age)

Expiry:
- **`get_expired_activities() -> list[Activity]`** — activities past their `expires_at`
- **`remove_expired() -> int`** — deletes expired activities (concert dates, event end times, etc.)

Type-aware expiry: a concert gets a hard `expires_at`, a restaurant doesn't, a hiking trail never expires (`NULL`).
No third-party dependencies — uses stdlib `sqlite3` and `json`.

## Conventions

- Python 3.10+ with full type annotations.
- `pyproject.toml`-based project (no `setup.py`).
- `src/` layout.
- Tests use `pytest` with class-based organization (`Test*` classes, `setup_method`).
- CLI tests use `typer.testing.CliRunner`.
- Do not add comments to code unless asked.
- Do not create documentation files (`*.md`) unless explicitly requested.

## Key models (src/activityfinder/models.py)

**`ActivityCategory`** — str Enum: sports, arts, music, food, outdoors, education, social, entertainment, other.

**`Activity`** dataclass:
- `title`, `description`, `category`, `location` (required)
- `start_time` (defaults to now), `end_time` (optional)
- `cost` (float, default 0.0), `tags` (list[str]), `source`, `url`
- `expires_at` (Optional[datetime], default None) — `None` = never expires

**`SearchCriteria`** dataclass:
- `query`, `categories`, `max_cost`, `location`, `tags` — all optional

## Indexer (src/activityfinder/indexer.py)

Simple in-memory list-based store:
- `index(activity)`, `index_many(activities)`, `remove(title) -> bool`, `all() -> list[Activity]`, `clear()`
- Requires a `Database` instance — delegates persistence on every mutation

## Recommender (src/activityfinder/recommender.py)

Filter-based search; applies each non-empty criterion as a narrowing filter:
1. query → substring match on title/description (case-insensitive)
2. categories → exact match
3. max_cost → `cost <= max_cost`
4. location → substring match (case-insensitive)
5. tags → any overlap

## CLI (src/activityfinder/cli.py)

Typer group `main` with four commands:

- `add` — index an activity (requires `--title`, `--description`, `--location`; optional `--category`, `--cost`, `--tags`, `--source`, `--url`, `--start-time`)
- `search` — search by `--query`, `--category` (repeatable), `--max-cost`, `--location`, `--tag` (repeatable)
- `list` — list all indexed activities
- `geogrid` — generate a geohash grid for a LOCATION argument (optional `--precision`, `--radius`)

The `list` command is registered as `@main.command(name="list")` with function name `list_activities` to avoid shadowing the built-in.

The `main` group accepts `--db` (also `ACTIVITYFINDER_DB` env var) to persist data to a SQLite file; defaults to `activityfinder.db`.

## Testing

```bash
.venv/bin/pytest -v
```

Tests are in `tests/`. Add test files alongside existing ones following the same class-per-module pattern. CLI tests should use `CliRunner` from `typer.testing`.
