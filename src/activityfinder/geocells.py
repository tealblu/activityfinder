import math
from dataclasses import dataclass, field

import httpx


class GeocellsError(Exception):
    pass


class GeocodeError(GeocellsError):
    pass


@dataclass
class Geocell:
    geohash: str
    latitude: float
    longitude: float
    precision: int


@dataclass
class Geogrid:
    location: str
    latitude: float
    longitude: float
    cells: list[Geocell] = field(default_factory=list)


BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

USER_AGENT = "activityfinder/0.1.0"


def _geohash_encode(lat: float, lng: float, precision: int) -> str:
    lat_min, lat_max = -90.0, 90.0
    lng_min, lng_max = -180.0, 180.0
    result: list[str] = []
    for i in range(precision):
        hash_val = 0
        for j in range(5):
            bit_global = i * 5 + j
            if bit_global % 2 == 0:
                mid = (lng_min + lng_max) / 2
                if lng >= mid:
                    hash_val |= 1 << (4 - j)
                    lng_min = mid
                else:
                    lng_max = mid
            else:
                mid = (lat_min + lat_max) / 2
                if lat >= mid:
                    hash_val |= 1 << (4 - j)
                    lat_min = mid
                else:
                    lat_max = mid
        result.append(BASE32[hash_val])
    return "".join(result)


def _geohash_decode_center(geohash: str) -> tuple[float, float]:
    lat_min, lat_max = -90.0, 90.0
    lng_min, lng_max = -180.0, 180.0
    for i, char in enumerate(geohash):
        val = BASE32.index(char)
        for j in range(5):
            bit = (val >> (4 - j)) & 1
            bit_global = i * 5 + j
            if bit_global % 2 == 0:
                mid = (lng_min + lng_max) / 2
                if bit:
                    lng_min = mid
                else:
                    lng_max = mid
            else:
                mid = (lat_min + lat_max) / 2
                if bit:
                    lat_min = mid
                else:
                    lat_max = mid
    return ((lat_min + lat_max) / 2, (lng_min + lng_max) / 2)


def _geohash_step(precision: int) -> tuple[float, float]:
    total_bits = 5 * precision
    lng_bits = (total_bits + 1) // 2
    lat_bits = total_bits // 2
    return (180.0 / (2**lat_bits), 360.0 / (2**lng_bits))


def resolve_area(query: str) -> dict:
    resp = httpx.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": query,
            "format": "json",
            "addressdetails": 1,
            "limit": 1,
            "bounded": 0,
        },
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise GeocodeError(f"Location not found: {query}")
    result = results[0]
    return {
        "display_name": result["display_name"],
        "bbox": result["boundingbox"],
        "lat": float(result["lat"]),
        "lng": float(result["lon"]),
        "type": result["type"],
    }


def geocode_location(location: str) -> tuple[float, float]:
    area = resolve_area(location)
    return (area["lat"], area["lng"])


MAX_GRID_CELLS = 10_000


def _auto_radius_km(bbox: list) -> float:
    min_lat, max_lat, min_lng, max_lng = map(float, bbox)
    center_lat = (min_lat + max_lat) / 2
    lat_km = (max_lat - min_lat) * 111.0
    lng_km = (max_lng - min_lng) * 111.0 * math.cos(math.radians(center_lat))
    return max(math.sqrt(lat_km**2 + lng_km**2) / 2, 0.5)


def _auto_precision(lat_extent: float, lng_extent: float) -> int:
    max_extent = max(lat_extent, lng_extent)
    if max_extent <= 0:
        return 7
    target = 10
    best = 1
    best_diff = abs(max_extent / max(_geohash_step(1)) - target)
    for p in range(2, 13):
        cells = max_extent / max(_geohash_step(p))
        diff = abs(cells - target)
        if diff < best_diff:
            best_diff = diff
            best = p
    return best


def generate_geogrid(
    location: str,
    precision: int | None = None,
    radius_km: float | None = None,
) -> Geogrid:
    area = resolve_area(location)
    center_lat = area["lat"]
    center_lng = area["lng"]
    display_name = area["display_name"]

    if radius_km is None:
        radius_km = _auto_radius_km(area["bbox"])

    if precision is None:
        lat_extent = 2 * radius_km / 111.0
        lng_extent = 2 * radius_km / (111.0 * math.cos(math.radians(center_lat)))
        precision = _auto_precision(lat_extent, lng_extent)

    lat_step, lng_step = _geohash_step(precision)
    lat_radius = radius_km / 111.0
    lng_radius = radius_km / (111.0 * math.cos(math.radians(center_lat)))

    min_lat = center_lat - lat_radius
    max_lat = center_lat + lat_radius
    min_lng = center_lng - lng_radius
    max_lng = center_lng + lng_radius

    n_lat = math.ceil((max_lat - min_lat) / lat_step)
    n_lng = math.ceil((max_lng - min_lng) / lng_step)
    if n_lat * n_lng > MAX_GRID_CELLS:
        raise GeocellsError(
            f"Grid too large: ~{n_lat * n_lng} cells at precision {precision}. "
            f"Reduce radius_km ({radius_km}) or precision ({precision})."
        )

    geohashes: set[str] = set()
    lat = min_lat
    while lat <= max_lat:
        lng = min_lng
        while lng <= max_lng:
            gh = _geohash_encode(lat, lng, precision)
            geohashes.add(gh)
            lng += lng_step
        lat += lat_step

    cells = []
    for gh in sorted(geohashes):
        cell_lat, cell_lng = _geohash_decode_center(gh)
        cells.append(
            Geocell(geohash=gh, latitude=cell_lat, longitude=cell_lng, precision=precision)
        )

    return Geogrid(
        location=display_name,
        latitude=center_lat,
        longitude=center_lng,
        cells=cells,
    )


def find_cell(
    cells: list[Geocell],
    latitude: float,
    longitude: float,
) -> Geocell | None:
    if not cells:
        return None
    precision = cells[0].precision
    target = _geohash_encode(latitude, longitude, precision)
    lookup = {c.geohash: c for c in cells}
    return lookup.get(target)
