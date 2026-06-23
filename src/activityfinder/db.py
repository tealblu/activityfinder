import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from activityfinder.models import Activity, ActivityCategory


_SQLITE_DT_FMT = "%Y-%m-%d %H:%M:%S"


def _dt_to_str(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime(_SQLITE_DT_FMT)


def _str_to_dt(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    return datetime.strptime(s, _SQLITE_DT_FMT)


class Database:
    def __init__(self, path: str = ":memory:"):
        self._path = str(path)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                refresh_cadence_seconds INTEGER NOT NULL DEFAULT 86400,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                location TEXT NOT NULL,
                latitude REAL NOT NULL DEFAULT 0.0,
                longitude REAL NOT NULL DEFAULT 0.0,
                geohash TEXT,
                start_time TEXT,
                end_time TEXT,
                cost REAL NOT NULL DEFAULT 0.0,
                tags TEXT NOT NULL DEFAULT '[]',
                source_id INTEGER REFERENCES sources(id),
                url TEXT DEFAULT '',
                expires_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_activities_geohash ON activities(geohash);
            CREATE INDEX IF NOT EXISTS idx_activities_category ON activities(category);
            CREATE INDEX IF NOT EXISTS idx_activities_expires ON activities(expires_at);

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
                text TEXT NOT NULL,
                rating REAL,
                author TEXT DEFAULT '',
                source_id INTEGER REFERENCES sources(id),
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_reviews_activity ON reviews(activity_id);

            CREATE TABLE IF NOT EXISTS cells_fetched (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                geohash TEXT NOT NULL,
                source TEXT NOT NULL,
                fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(geohash, source)
            );
        """)

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def get_or_create_source(self, name: str, refresh_cadence_seconds: int = 86400) -> int:
        if not name:
            return 0
        self._conn.execute(
            "INSERT OR IGNORE INTO sources (name, refresh_cadence_seconds) VALUES (?, ?)",
            (name, refresh_cadence_seconds),
        )
        row = self._conn.execute(
            "SELECT id FROM sources WHERE name = ?", (name,)
        ).fetchone()
        return row["id"]

    def get_source(self, name: str) -> Optional[dict[str, Any]]:
        row = self._conn.execute(
            "SELECT * FROM sources WHERE name = ?", (name,)
        ).fetchone()
        return dict(row) if row else None

    def list_sources(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM sources ORDER BY name"
        ).fetchall()]

    # ------------------------------------------------------------------
    # Activities
    # ------------------------------------------------------------------

    def add_activity(
        self,
        activity: Activity,
        source_name: str = "",
        latitude: float = 0.0,
        longitude: float = 0.0,
        geohash: str = "",
    ) -> int:
        source_id: Optional[int] = None
        src = source_name or activity.source
        if src:
            source_id = self.get_or_create_source(
                src, refresh_cadence_seconds=self._cadence_for_source(src)
            )
        tags_json = json.dumps(activity.tags)
        start_str = _dt_to_str(activity.start_time)
        end_str = _dt_to_str(activity.end_time)
        expires_str = _dt_to_str(activity.expires_at)

        cur = self._conn.execute(
            """INSERT INTO activities
               (title, description, category, location, latitude, longitude, geohash,
                start_time, end_time, cost, tags, source_id, url, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                activity.title, activity.description, activity.category.value,
                activity.location, latitude, longitude, geohash,
                start_str, end_str, activity.cost, tags_json, source_id,
                activity.url, expires_str,
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def remove_activity(self, title: str) -> bool:
        cur = self._conn.execute("DELETE FROM activities WHERE title = ?", (title,))
        self._conn.commit()
        return cur.rowcount > 0

    def get_activity_by_title(self, title: str) -> Optional[Activity]:
        row = self._conn.execute(
            """SELECT a.*, s.name AS source_name
               FROM activities a
               LEFT JOIN sources s ON a.source_id = s.id
               WHERE a.title = ?""",
            (title,),
        ).fetchone()
        return self._row_to_activity(row) if row else None

    def get_activity_by_id(self, activity_id: int) -> Optional[dict[str, Any]]:
        row = self._conn.execute(
            """SELECT a.*, s.name AS source_name
               FROM activities a
               LEFT JOIN sources s ON a.source_id = s.id
               WHERE a.id = ?""",
            (activity_id,),
        ).fetchone()
        return dict(row) if row else None

    def all_activities(self) -> list[Activity]:
        rows = self._conn.execute(
            """SELECT a.*, s.name AS source_name
               FROM activities a
               LEFT JOIN sources s ON a.source_id = s.id
               ORDER BY a.created_at DESC"""
        ).fetchall()
        return [self._row_to_activity(r) for r in rows]

    def search_activities(
        self,
        query: str = "",
        category: Optional[str] = None,
        max_cost: Optional[float] = None,
        location: str = "",
        tag: str = "",
    ) -> list[Activity]:
        sql = """SELECT a.*, s.name AS source_name
                 FROM activities a
                 LEFT JOIN sources s ON a.source_id = s.id
                 WHERE 1=1"""
        params: list[Any] = []

        if query:
            sql += " AND (a.title LIKE ? OR a.description LIKE ?)"
            like = f"%{query}%"
            params.extend([like, like])

        if category:
            sql += " AND a.category = ?"
            params.append(category)

        if max_cost is not None:
            sql += " AND a.cost <= ?"
            params.append(max_cost)

        if location:
            sql += " AND a.location LIKE ?"
            params.append(f"%{location}%")

        if tag:
            sql += " AND a.tags LIKE ?"
            params.append(f"%{tag}%")

        sql += " ORDER BY a.created_at DESC"

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_activity(r) for r in rows]

    def clear_activities(self) -> None:
        self._conn.execute("DELETE FROM activities")
        self._conn.commit()

    def _cadence_for_source(self, name: str) -> int:
        if not name:
            return 86400
        row = self._conn.execute(
            "SELECT refresh_cadence_seconds FROM sources WHERE name = ?", (name,)
        ).fetchone()
        if row:
            return row["refresh_cadence_seconds"]
        return 86400

    def _row_to_activity(self, row: sqlite3.Row) -> Activity:
        return Activity(
            title=row["title"],
            description=row["description"],
            category=ActivityCategory(row["category"]),
            location=row["location"],
            start_time=_str_to_dt(row["start_time"]) or datetime.now(),
            end_time=_str_to_dt(row["end_time"]),
            cost=row["cost"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            source=row["source_name"] if row["source_name"] else "",
            url=row["url"] or "",
            expires_at=_str_to_dt(row["expires_at"]),
        )

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    def add_review(
        self,
        activity_id: int,
        text: str,
        rating: Optional[float] = None,
        author: str = "",
        source_name: str = "",
    ) -> int:
        source_id: Optional[int] = self.get_or_create_source(source_name) if source_name else None
        cur = self._conn.execute(
            "INSERT INTO reviews (activity_id, text, rating, author, source_id) VALUES (?, ?, ?, ?, ?)",
            (activity_id, text, rating, author, source_id),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_reviews(self, activity_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT r.*, s.name AS source_name
               FROM reviews r
               LEFT JOIN sources s ON r.source_id = s.id
               WHERE r.activity_id = ?
               ORDER BY r.created_at DESC""",
            (activity_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Cells Fetched Cache
    # ------------------------------------------------------------------

    def is_cell_fetched(self, geohash: str, source: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM cells_fetched WHERE geohash = ? AND source = ?",
            (geohash, source),
        ).fetchone()
        return row is not None

    def mark_cell_fetched(self, geohash: str, source: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO cells_fetched (geohash, source, fetched_at) VALUES (?, ?, datetime('now'))",
            (geohash, source),
        )
        self._conn.commit()

    def get_stale_cells(self, source: str, max_age_seconds: Optional[int] = None) -> list[dict[str, Any]]:
        if max_age_seconds is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)).strftime(_SQLITE_DT_FMT)
            rows = self._conn.execute(
                """SELECT cf.*, 'manual' AS cadence_source
                   FROM cells_fetched cf
                   WHERE cf.source = ?
                   AND cf.fetched_at < ?
                   ORDER BY cf.fetched_at ASC""",
                (source, cutoff),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT cf.*, s.refresh_cadence_seconds AS cadence_source
                   FROM cells_fetched cf
                   JOIN sources s ON s.name = cf.source
                   WHERE cf.source = ?
                   AND cf.fetched_at < datetime('now', '-' || s.refresh_cadence_seconds || ' seconds')
                   ORDER BY cf.fetched_at ASC""",
                (source,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Expired activities
    # ------------------------------------------------------------------

    def get_expired_activities(self) -> list[Activity]:
        rows = self._conn.execute(
            """SELECT a.*, s.name AS source_name
               FROM activities a
               LEFT JOIN sources s ON a.source_id = s.id
               WHERE a.expires_at IS NOT NULL AND a.expires_at < datetime('now')
               ORDER BY a.expires_at ASC"""
        ).fetchall()
        return [self._row_to_activity(r) for r in rows]

    def remove_expired(self) -> int:
        cur = self._conn.execute(
            "DELETE FROM activities WHERE expires_at IS NOT NULL AND expires_at < datetime('now')"
        )
        self._conn.commit()
        return cur.rowcount

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
