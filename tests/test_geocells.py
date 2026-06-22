from activityfinder.geocells import Geocell, find_cell, _geohash_encode


class TestFindCell:
    def setup_method(self) -> None:
        self.cells = [
            Geocell(geohash="u4pruydqqvj", latitude=57.64911, longitude=10.40744, precision=11),
            Geocell(geohash="u4pruydqqvk", latitude=57.64911, longitude=10.40759, precision=11),
            Geocell(geohash="u4pruydqqvm", latitude=57.64913, longitude=10.40744, precision=11),
        ]

    def test_finds_exact_match(self) -> None:
        cell = find_cell(self.cells, 57.64911, 10.40744)
        assert cell is not None
        assert cell.geohash == "u4pruydqqvj"

    def test_returns_none_for_mismatch(self) -> None:
        cell = find_cell(self.cells, 0.0, 0.0)
        assert cell is None

    def test_returns_none_for_empty_list(self) -> None:
        cell = find_cell([], 57.64911, 10.40744)
        assert cell is None

    def test_matches_encoded_geohash(self) -> None:
        lat, lng = 40.7128, -74.0060
        precision = 6
        expected_hash = _geohash_encode(lat, lng, precision)
        cells = [Geocell(geohash=expected_hash, latitude=lat, longitude=lng, precision=precision)]
        result = find_cell(cells, lat, lng)
        assert result is not None
        assert result.geohash == expected_hash
