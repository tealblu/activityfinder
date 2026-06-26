import os
from typing import Any, Optional

import httpx

from activityfinder.geocells import Geocell, Geogrid, geocode_location
from activityfinder.models import Activity, ActivityCategory


class FoursquareError(Exception):
    pass


class FoursquareAPIError(FoursquareError):
    pass


# Map Foursquare top-level category IDs to ActivityCategory
# https://developer.foursquare.com/docs/categories
FOURSQUARE_CATEGORY_MAP: dict[str, ActivityCategory] = {
    "10000": ActivityCategory.ENTERTAINMENT,  # Arts & Entertainment
    "11000": ActivityCategory.MUSIC,          # Music Venues
    "12000": ActivityCategory.EDUCATION,      # College & University
    "13000": ActivityCategory.FOOD,           # Food
    "14000": ActivityCategory.OTHER,          # Shop & Service
    "15000": ActivityCategory.OTHER,          # Travel & Transport
    "16000": ActivityCategory.SOCIAL,         # Nightlife
    "17000": ActivityCategory.OUTDOORS,       # Outdoors & Recreation
    "18000": ActivityCategory.SPORTS,         # Sports & Recreation
}

FOURSQUARE_API_VERSION = "2025-06-17"
FOURSQUARE_DEFAULT_API_URL = "https://places-api.foursquare.com/places"
FOURSQUARE_DEFAULT_RADIUS_M = 1000
FOURSQUARE_DEFAULT_LIMIT = 50
FOURSQUARE_MAX_LIMIT = 50

# Default fields requested from the Places API
FOURSQUARE_DEFAULT_FIELDS = (
    "fsq_place_id,name,location,categories,website"
)


class FoursquareClient:
    """Client for the Foursquare Places API.

    Targets the new places-api.foursquare.com endpoint with
    Bearer auth and X-Places-Api-Version header.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: str = FOURSQUARE_DEFAULT_API_URL,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("FOURSQUARE_API_KEY") or ""
        if not self._api_key:
            raise FoursquareError(
                "FOURSQUARE_API_KEY environment variable not set"
            )
        self._api_url = api_url.rstrip("/")
        self._client = client or httpx.Client()

    # ------------------------------------------------------------------
    # Core request
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.get(
            f"{self._api_url}{path}",
            params=params,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "X-Places-Api-Version": FOURSQUARE_API_VERSION,
                "Accept": "application/json",
            },
        )
        if resp.status_code == 401:
            raise FoursquareAPIError("Invalid Foursquare API key")
        if resp.status_code == 429:
            raise FoursquareAPIError("Foursquare API rate limit exceeded")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_places(
        self,
        ll: Optional[str] = None,
        near: Optional[str] = None,
        radius: int = FOURSQUARE_DEFAULT_RADIUS_M,
        query: str = "",
        fsq_category_ids: Optional[str] = None,
        limit: int = FOURSQUARE_DEFAULT_LIMIT,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "limit": min(limit, FOURSQUARE_MAX_LIMIT),
            "fields": FOURSQUARE_DEFAULT_FIELDS,
        }
        if ll:
            params["ll"] = ll
        elif near:
            params["near"] = near
        if radius:
            params["radius"] = radius
        if query:
            params["query"] = query
        if fsq_category_ids:
            params["fsq_category_ids"] = fsq_category_ids

        data = self._get("/search", params)
        return data.get("results", [])

    def search_by_location(
        self,
        location: str,
        query: str = "",
        radius_m: int = FOURSQUARE_DEFAULT_RADIUS_M,
        limit: int = FOURSQUARE_DEFAULT_LIMIT,
        category_ids: Optional[str] = None,
    ) -> list[tuple[Activity, list[dict[str, Any]]]]:
        lat, lng = geocode_location(location)
        return self.search_by_coords(
            lat, lng, query=query, radius_m=radius_m,
            limit=limit, category_ids=category_ids,
            location_name=location,
        )

    def search_by_coords(
        self,
        latitude: float,
        longitude: float,
        query: str = "",
        radius_m: int = FOURSQUARE_DEFAULT_RADIUS_M,
        limit: int = FOURSQUARE_DEFAULT_LIMIT,
        category_ids: Optional[str] = None,
        location_name: str = "",
    ) -> list[tuple[Activity, list[dict[str, Any]]]]:
        ll_str = f"{latitude},{longitude}"
        places = self.search_places(
            ll=ll_str, radius=radius_m, query=query,
            fsq_category_ids=category_ids, limit=limit,
        )
        results: list[tuple[Activity, list[dict[str, Any]]]] = []
        for p in places:
            activity, fsq_place_id = self._place_to_activity(p, location_name)
            tips = self.get_place_tips(fsq_place_id) if fsq_place_id else []
            results.append((activity, tips))
        return results

    def search_cell(
        self,
        cell: Geocell,
        query: str = "",
        radius_m: int = FOURSQUARE_DEFAULT_RADIUS_M,
        limit: int = FOURSQUARE_DEFAULT_LIMIT,
    ) -> list[tuple[Activity, list[dict[str, Any]]]]:
        return self.search_by_coords(
            cell.latitude, cell.longitude,
            query=query, radius_m=radius_m, limit=limit,
        )

    def search_grid(
        self,
        grid: Geogrid,
        query: str = "",
        limit: int = FOURSQUARE_DEFAULT_LIMIT,
        radius_m: Optional[int] = None,
        db: Optional[Any] = None,
    ) -> list[tuple[Activity, list[dict[str, Any]]]]:
        results: list[tuple[Activity, list[dict[str, Any]]]] = []
        source_name = "foursquare"

        for cell in grid.cells:
            if db is not None and db.is_cell_fetched(cell.geohash, source_name):
                continue

            cell_results = self.search_cell(
                cell, query=query, limit=limit,
                radius_m=radius_m or FOURSQUARE_DEFAULT_RADIUS_M,
            )
            results.extend(cell_results)

            if db is not None:
                db.mark_cell_fetched(cell.geohash, source_name)

        return results

    # ------------------------------------------------------------------
    # Place details
    # ------------------------------------------------------------------

    def get_place(self, fsq_place_id: str) -> dict[str, Any]:
        return self._get(f"/{fsq_place_id}", {"fields": FOURSQUARE_DEFAULT_FIELDS})

    def get_place_photos(self, fsq_place_id: str, limit: int = 10) -> list[dict[str, Any]]:
        data = self._get(f"/{fsq_place_id}/photos", {"limit": min(limit, FOURSQUARE_MAX_LIMIT)})
        return data if isinstance(data, list) else []

    def get_place_tips(self, fsq_place_id: str, limit: int = 10) -> list[dict[str, Any]]:
        data = self._get(f"/{fsq_place_id}/tips", {"limit": min(limit, FOURSQUARE_MAX_LIMIT)})
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_category(fsq_categories: list[dict[str, Any]]) -> ActivityCategory:
        if not fsq_categories:
            return ActivityCategory.OTHER
        for cat in fsq_categories:
            cat_id = cat.get("fsq_category_id", cat.get("id", ""))
            if cat_id in FOURSQUARE_CATEGORY_MAP:
                return FOURSQUARE_CATEGORY_MAP[cat_id]
        return ActivityCategory.OTHER

    @staticmethod
    def _build_tags(fsq_categories: list[dict[str, Any]]) -> list[str]:
        return [
            cat["name"].lower().replace(" ", "_")
            for cat in fsq_categories
            if cat.get("name")
        ]

    @staticmethod
    def _format_location(
        location_data: dict[str, Any],
        location_name: str = "",
    ) -> str:
        if location_data.get("formatted_address"):
            return location_data["formatted_address"]
        parts = []
        if location_data.get("address"):
            parts.append(location_data["address"])
        if location_data.get("locality"):
            parts.append(location_data["locality"])
        if location_data.get("region"):
            parts.append(location_data["region"])
        return ", ".join(parts) if parts else location_name

    def _place_to_activity(
        self,
        place: dict[str, Any],
        location_name: str = "",
    ) -> tuple[Activity, str]:
        name = place.get("name", "Unknown")
        categories = place.get("categories", [])
        cat_names = [c.get("name", "") for c in categories]
        desc = ", ".join(c for c in cat_names if c) or name

        location_data = place.get("location", {})
        address = self._format_location(location_data, location_name)

        fsq_place_id = place.get("fsq_place_id", "")
        url = place.get("website", "")
        if not url and fsq_place_id:
            url = f"https://foursquare.com/v/{fsq_place_id}"

        return (
            Activity(
                title=name,
                description=desc,
                category=self._map_category(categories),
                location=address,
                cost=0.0,
                tags=self._build_tags(categories),
                source="foursquare",
                url=url,
            ),
            fsq_place_id,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "FoursquareClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
