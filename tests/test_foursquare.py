from unittest.mock import MagicMock, patch

import httpx
import pytest

from activityfinder.foursquare import (
    FOURSQUARE_API_VERSION,
    FOURSQUARE_CATEGORY_MAP,
    FoursquareAPIError,
    FoursquareClient,
    FoursquareError,
)
from activityfinder.geocells import Geocell, Geogrid
from activityfinder.models import Activity, ActivityCategory


SAMPLE_PLACE = {
    "fsq_place_id": "abc123",
    "name": "Test Place",
    "categories": [{"fsq_category_id": "13000", "name": "Restaurant"}],
    "location": {
        "address": "123 Main St",
        "locality": "Portland",
        "region": "OR",
        "formatted_address": "123 Main St, Portland, OR",
    },
    "website": "https://example.com/test-place",
}

SAMPLE_PLACE_NO_FORMATTED = {
    "fsq_place_id": "def456",
    "name": "No Format",
    "categories": [{"fsq_category_id": "17000", "name": "Park"}],
    "location": {
        "address": "456 Oak Ave",
        "locality": "Seattle",
        "region": "WA",
    },
}

SAMPLE_PLACE_MINIMAL = {
    "fsq_place_id": "",
    "name": "Minimal",
    "categories": [],
    "location": {},
}


class TestFoursquareClientInit:
    def test_requires_api_key(self) -> None:
        with patch.dict("os.environ", clear=True):
            with pytest.raises(FoursquareError, match="FOURSQUARE_API_KEY"):
                FoursquareClient()

    def test_uses_env_var(self) -> None:
        with patch.dict("os.environ", {"FOURSQUARE_API_KEY": "env-key"}):
            client = FoursquareClient()
            assert client._api_key == "env-key"
            client.close()

    def test_explicit_key_overrides_env(self) -> None:
        with patch.dict("os.environ", {"FOURSQUARE_API_KEY": "env-key"}):
            client = FoursquareClient(api_key="explicit")
            assert client._api_key == "explicit"
            client.close()

    def test_custom_client(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        with patch.dict("os.environ", {"FOURSQUARE_API_KEY": "key"}):
            client = FoursquareClient(client=mock_client)
            assert client._client is mock_client
            client.close()

    def test_context_manager(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        with patch.dict("os.environ", {"FOURSQUARE_API_KEY": "key"}):
            with FoursquareClient(client=mock_client) as client:
                assert client._client is mock_client
            mock_client.close.assert_called_once()


class TestFoursquareClientGet:
    def setup_method(self) -> None:
        self.mock_httpx = MagicMock(spec=httpx.Client)
        self.client = FoursquareClient(
            api_key="test-key", client=self.mock_httpx
        )
        self.expected_headers = {
            "Authorization": "Bearer test-key",
            "X-Places-Api-Version": FOURSQUARE_API_VERSION,
            "Accept": "application/json",
        }

    def test_successful_get(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": []}
        )
        result = self.client._get("/search", {"limit": 10})
        assert result == {"results": []}
        self.mock_httpx.get.assert_called_once_with(
            "https://places-api.foursquare.com/places/search",
            params={"limit": 10},
            headers=self.expected_headers,
        )

    def test_401_error(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(status_code=401)
        with pytest.raises(FoursquareAPIError, match="Invalid"):
            self.client._get("/search", {})

    def test_429_error(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(status_code=429)
        with pytest.raises(FoursquareAPIError, match="rate limit"):
            self.client._get("/search", {})

    def test_other_http_error(self) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(spec=httpx.Request),
            response=mock_response,
        )
        self.mock_httpx.get.return_value = mock_response
        with pytest.raises(httpx.HTTPStatusError):
            self.client._get("/search", {})


class TestFoursquareClientSearch:
    def setup_method(self) -> None:
        self.mock_httpx = MagicMock(spec=httpx.Client)
        self.client = FoursquareClient(
            api_key="test-key", client=self.mock_httpx
        )

    def test_search_places_with_ll(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": [SAMPLE_PLACE]}
        )
        results = self.client.search_places(ll="45.5,-122.6", query="coffee", limit=10)
        assert len(results) == 1
        assert results[0]["name"] == "Test Place"
        call_params = self.mock_httpx.get.call_args[1]["params"]
        assert call_params["ll"] == "45.5,-122.6"
        assert call_params["query"] == "coffee"
        assert call_params["limit"] == 10

    def test_search_places_with_near(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": []}
        )
        self.client.search_places(near="Portland, OR")
        call_params = self.mock_httpx.get.call_args[1]["params"]
        assert call_params["near"] == "Portland, OR"

    def test_search_places_clamps_limit(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": []}
        )
        self.client.search_places(ll="0,0", limit=999)
        call_params = self.mock_httpx.get.call_args[1]["params"]
        assert call_params["limit"] == 50

    def test_search_places_with_category_ids(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": []}
        )
        self.client.search_places(ll="0,0", fsq_category_ids="13000,17000")
        call_params = self.mock_httpx.get.call_args[1]["params"]
        assert call_params["fsq_category_ids"] == "13000,17000"

    def test_search_places_includes_fields(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": []}
        )
        self.client.search_places(ll="0,0")
        call_params = self.mock_httpx.get.call_args[1]["params"]
        assert call_params["fields"] == "fsq_place_id,name,location,categories,website"

    @patch("activityfinder.foursquare.geocode_location")
    def test_search_by_location(self, mock_geocode) -> None:
        mock_geocode.return_value = (45.5, -122.6)
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": [SAMPLE_PLACE]}
        )
        activities = self.client.search_by_location("Portland, OR", query="coffee")
        assert len(activities) == 1
        assert isinstance(activities[0], Activity)
        assert activities[0].title == "Test Place"
        mock_geocode.assert_called_once_with("Portland, OR")

    def test_search_by_coords(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": [SAMPLE_PLACE]}
        )
        activities = self.client.search_by_coords(45.5, -122.6, location_name="Portland")
        assert len(activities) == 1
        assert activities[0].location == "123 Main St, Portland, OR"

    def test_search_cell(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": [SAMPLE_PLACE]}
        )
        cell = Geocell(geohash="abc", latitude=45.5, longitude=-122.6, precision=8)
        activities = self.client.search_cell(cell, query="food")
        assert len(activities) == 1


class TestFoursquareClientSearchGrid:
    def setup_method(self) -> None:
        self.mock_httpx = MagicMock(spec=httpx.Client)
        self.client = FoursquareClient(
            api_key="test-key", client=self.mock_httpx
        )
        self.grid = Geogrid(
            location="Portland",
            latitude=45.5,
            longitude=-122.6,
            cells=[
                Geocell(geohash="a1", latitude=45.5, longitude=-122.6, precision=6),
                Geocell(geohash="b2", latitude=45.6, longitude=-122.5, precision=6),
                Geocell(geohash="c3", latitude=45.4, longitude=-122.7, precision=6),
            ],
        )

    def test_searches_all_cells(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": [SAMPLE_PLACE]}
        )
        results = self.client.search_grid(self.grid, query="pizza")
        assert len(results) == 3
        assert self.mock_httpx.get.call_count == 3

    def test_skips_fetched_cells_when_db_provided(self) -> None:
        mock_db = MagicMock()
        mock_db.is_cell_fetched.side_effect = lambda gh, src: gh == "a1"
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": [SAMPLE_PLACE]}
        )
        results = self.client.search_grid(self.grid, query="pizza", db=mock_db)
        assert len(results) == 2
        assert self.mock_httpx.get.call_count == 2

    def test_marks_cells_fetched(self) -> None:
        mock_db = MagicMock()
        mock_db.is_cell_fetched.return_value = False
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: {"results": [SAMPLE_PLACE]}
        )
        self.client.search_grid(self.grid, query="pizza", db=mock_db)
        assert mock_db.mark_cell_fetched.call_count == 3
        mock_db.mark_cell_fetched.assert_any_call("a1", "foursquare")
        mock_db.mark_cell_fetched.assert_any_call("b2", "foursquare")
        mock_db.mark_cell_fetched.assert_any_call("c3", "foursquare")


class TestFoursquareClientDetails:
    def setup_method(self) -> None:
        self.mock_httpx = MagicMock(spec=httpx.Client)
        self.client = FoursquareClient(
            api_key="test-key", client=self.mock_httpx
        )

    def test_get_place(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: {"fsq_place_id": "abc", "name": "Place"}
        )
        result = self.client.get_place("abc")
        assert result["name"] == "Place"

    def test_get_place_photos(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: [{"id": "p1"}]
        )
        result = self.client.get_place_photos("abc")
        assert len(result) == 1

    def test_get_place_photos_non_list(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: {"error": "not a list"}
        )
        result = self.client.get_place_photos("abc")
        assert result == []

    def test_get_place_tips(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: [{"id": "t1"}]
        )
        result = self.client.get_place_tips("abc")
        assert len(result) == 1

    def test_get_place_tips_non_list(self) -> None:
        self.mock_httpx.get.return_value = MagicMock(
            status_code=200, json=lambda: {}
        )
        result = self.client.get_place_tips("abc")
        assert result == []


class TestMapCategory:
    def test_maps_known_category_with_new_field_name(self) -> None:
        for fsq_id, expected in FOURSQUARE_CATEGORY_MAP.items():
            result = FoursquareClient._map_category([{"fsq_category_id": fsq_id}])
            assert result == expected, f"{fsq_id} -> {expected}"

    def test_maps_known_category_with_legacy_field_name(self) -> None:
        result = FoursquareClient._map_category([{"id": "13000"}])
        assert result == ActivityCategory.FOOD

    def test_maps_unknown_category_to_other(self) -> None:
        result = FoursquareClient._map_category([{"fsq_category_id": "99999"}])
        assert result == ActivityCategory.OTHER

    def test_maps_empty_list_to_other(self) -> None:
        result = FoursquareClient._map_category([])
        assert result == ActivityCategory.OTHER

    def test_uses_first_matching_category(self) -> None:
        cats = [{"fsq_category_id": "99999"}, {"fsq_category_id": "13000"}, {"fsq_category_id": "17000"}]
        result = FoursquareClient._map_category(cats)
        assert result == ActivityCategory.FOOD


class TestBuildTags:
    def test_builds_tags_from_category_names(self) -> None:
        cats = [{"name": "Restaurant"}, {"name": "Italian"}]
        tags = FoursquareClient._build_tags(cats)
        assert tags == ["restaurant", "italian"]

    def test_handles_spaces_in_names(self) -> None:
        cats = [{"name": "Outdoors & Recreation"}]
        tags = FoursquareClient._build_tags(cats)
        assert tags == ["outdoors_&_recreation"]

    def test_returns_empty_for_empty_categories(self) -> None:
        assert FoursquareClient._build_tags([]) == []

    def test_skips_categories_without_name(self) -> None:
        cats = [{"fsq_category_id": "13000"}, {"name": "Restaurant"}]
        tags = FoursquareClient._build_tags(cats)
        assert tags == ["restaurant"]


class TestFormatLocation:
    def test_uses_formatted_address_when_available(self) -> None:
        loc = {"formatted_address": "123 Main St, Portland, OR"}
        result = FoursquareClient._format_location(loc)
        assert result == "123 Main St, Portland, OR"

    def test_builds_from_parts(self) -> None:
        loc = {"address": "456 Oak Ave", "locality": "Seattle", "region": "WA"}
        result = FoursquareClient._format_location(loc)
        assert result == "456 Oak Ave, Seattle, WA"

    def test_uses_location_name_when_no_address(self) -> None:
        result = FoursquareClient._format_location({}, "Fallback City")
        assert result == "Fallback City"

    def test_returns_empty_string_when_no_data(self) -> None:
        result = FoursquareClient._format_location({})
        assert result == ""


class TestPlaceToActivity:
    def setup_method(self) -> None:
        self.mock_httpx = MagicMock(spec=httpx.Client)
        self.client = FoursquareClient(
            api_key="test-key", client=self.mock_httpx
        )

    def test_converts_full_place(self) -> None:
        activity = self.client._place_to_activity(SAMPLE_PLACE, "Portland")
        assert activity.title == "Test Place"
        assert activity.description == "Restaurant"
        assert activity.category == ActivityCategory.FOOD
        assert activity.location == "123 Main St, Portland, OR"
        assert activity.cost == 0.0
        assert activity.tags == ["restaurant"]
        assert activity.source == "foursquare"
        assert activity.url == "https://example.com/test-place"

    def test_converts_place_without_formatted_address(self) -> None:
        activity = self.client._place_to_activity(SAMPLE_PLACE_NO_FORMATTED, "Seattle")
        assert activity.title == "No Format"
        assert activity.category == ActivityCategory.OUTDOORS
        assert activity.location == "456 Oak Ave, Seattle, WA"

    def test_converts_minimal_place(self) -> None:
        activity = self.client._place_to_activity(SAMPLE_PLACE_MINIMAL)
        assert activity.title == "Minimal"
        assert activity.description == "Minimal"
        assert activity.category == ActivityCategory.OTHER
        assert activity.location == ""
        assert activity.tags == []
        assert activity.url == ""

    def test_generates_url_from_fsq_place_id(self) -> None:
        place = dict(SAMPLE_PLACE_MINIMAL, fsq_place_id="my-id")
        activity = self.client._place_to_activity(place)
        assert activity.url == "https://foursquare.com/v/my-id"

    def test_prefers_website_over_generated_url(self) -> None:
        place = dict(SAMPLE_PLACE_MINIMAL, fsq_place_id="my-id", website="https://mine.example.com")
        activity = self.client._place_to_activity(place)
        assert activity.url == "https://mine.example.com"

    def test_description_from_categories(self) -> None:
        place = {
            "name": "Best Pizza",
            "categories": [{"fsq_category_id": "13000", "name": "Pizza Place"}],
            "location": {},
        }
        activity = self.client._place_to_activity(place)
        assert activity.description == "Pizza Place"

    def test_falls_back_to_name_for_description(self) -> None:
        place = {"name": "Nameless Cafe", "categories": [], "location": {}}
        activity = self.client._place_to_activity(place)
        assert activity.description == "Nameless Cafe"
