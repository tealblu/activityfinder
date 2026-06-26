from typing import Optional

from activityfinder.db import Database
from activityfinder.foursquare import FoursquareClient
from activityfinder.geocells import generate_geogrid
from activityfinder.models import Activity


class Indexer:
    def __init__(self, db: Database) -> None:
        self._activities: list[Activity] = db.all_activities()
        self._db = db

    def index(self, activity: Activity) -> None:
        self._activities.append(activity)
        self._db.add_activity(activity)

    def index_many(self, activities: list[Activity]) -> None:
        self._activities.extend(activities)
        for a in activities:
            self._db.add_activity(a)

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
    ) -> list[Activity]:
        """Search Foursquare by location and index results."""
        with FoursquareClient() as client:
            results = client.search_by_location(
                location=location,
                query=query,
                radius_m=radius_m,
                limit=limit,
                category_ids=category_ids,
            )
        self.index_many(results)
        return results

    def foursquare_grid_search_and_index(
        self,
        location: str,
        query: str = "",
        precision: Optional[int] = None,
        radius_km: Optional[float] = None,
        radius_m: Optional[int] = None,
        limit: int = 50,
    ) -> list[Activity]:
        """Generate a geohash grid, search each cell on Foursquare, and index results."""
        grid = generate_geogrid(location, precision=precision, radius_km=radius_km)
        with FoursquareClient() as client:
            results = client.search_grid(
                grid=grid, query=query, limit=limit, radius_m=radius_m, db=self._db,
            )
        self.index_many(results)
        return results

    def __len__(self) -> int:
        return len(self._activities)
