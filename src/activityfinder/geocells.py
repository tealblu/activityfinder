from dataclasses import dataclass, field
from typing import Optional


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


def geocode_location(location: str) -> tuple[float, float]:
    raise NotImplementedError


def generate_geogrid(
    location: str,
    precision: int = 7,
    radius_km: float = 5.0,
) -> Geogrid:
    raise NotImplementedError
