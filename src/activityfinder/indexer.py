from typing import Any, Optional

from activityfinder.db import Database
from activityfinder.foursquare import FoursquareClient
from activityfinder.geocells import generate_geogrid
from activityfinder.models import Activity


class Indexer:
    def __init__(self, db: Database) -> None:
        self._activities: list[Activity] = db.all_activities()
        self._db = db

    def index(self, activity: Activity, tips: Optional[list[dict[str, Any]]] = None) -> int:
        activity_id = self._db.add_activity(activity)
        self._activities.append(activity)
        self._store_tips(activity_id, tips or [])
        return activity_id

    def index_many(self, activities: list[Activity]) -> None:
        self._activities.extend(activities)
        for a in activities:
            self._db.add_activity(a)

    def _store_tips(self, activity_id: int, tips: list[dict[str, Any]]) -> None:
        for tip in tips:
            text = tip.get("text", "")
            if not text:
                continue
            user = tip.get("user", {}) or {}
            author = user.get("name", "") if isinstance(user, dict) else ""
            self._db.add_review(
                activity_id=activity_id,
                text=text,
                author=author,
                source_name="foursquare",
            )

    def remove(self, title: str) -> bool:
        for i, a in enumerate(self._activities):
            if a.title == title:
                del self._activities[i]
                self._db.remove_activity(title)
                return True
        return False

    def all(self) -> list[Activity]:
        return list(self._activities)

    def clear(self) -> None:
        self._activities.clear()
        self._db.clear_activities()

    def foursquare_search_and_index(
        self,
        location: str,
        query: str = "",
        radius_m: int = 1000,
        limit: int = 50,
        category_ids: Optional[str] = None,
    ) -> list[tuple[Activity, list[dict[str, Any]]]]:
        """Search Foursquare by location and index results."""
        with FoursquareClient() as client:
            results = client.search_by_location(
                location=location,
                query=query,
                radius_m=radius_m,
                limit=limit,
                category_ids=category_ids,
            )
        for activity, tips in results:
            self.index(activity, tips=tips)
        return results

    def foursquare_grid_search_and_index(
        self,
        location: str,
        query: str = "",
        precision: Optional[int] = None,
        radius_km: Optional[float] = None,
        radius_m: Optional[int] = None,
        limit: int = 50,
    ) -> list[tuple[Activity, list[dict[str, Any]]]]:
        """Generate a geohash grid, search each cell on Foursquare, and index results."""
        grid = generate_geogrid(location, precision=precision, radius_km=radius_km)
        with FoursquareClient() as client:
            results = client.search_grid(
                grid=grid, query=query, limit=limit, radius_m=radius_m, db=self._db,
            )
        for activity, tips in results:
            self.index(activity, tips=tips)
        return results

    def __len__(self) -> int:
        return len(self._activities)
