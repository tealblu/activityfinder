import json
from datetime import datetime, timedelta, timezone

from activityfinder.db import Database
from activityfinder.models import Activity, ActivityCategory


class TestDatabase:
    def setup_method(self) -> None:
        self.db = Database(":memory:")

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def test_get_or_create_source_creates(self) -> None:
        sid = self.db.get_or_create_source("test_source", 3600)
        assert sid > 0
        src = self.db.get_source("test_source")
        assert src is not None
        assert src["name"] == "test_source"
        assert src["refresh_cadence_seconds"] == 3600

    def test_get_or_create_source_reuses(self) -> None:
        sid1 = self.db.get_or_create_source("dup", 3600)
        sid2 = self.db.get_or_create_source("dup", 7200)
        assert sid1 == sid2
        src = self.db.get_source("dup")
        assert src["refresh_cadence_seconds"] == 3600

    def test_get_or_create_source_empty(self) -> None:
        assert self.db.get_or_create_source("") == 0

    def test_get_source_nonexistent(self) -> None:
        assert self.db.get_source("nope") is None

    def test_list_sources(self) -> None:
        self.db.get_or_create_source("a", 100)
        self.db.get_or_create_source("b", 200)
        names = [s["name"] for s in self.db.list_sources()]
        assert names == ["a", "b"]

    # ------------------------------------------------------------------
    # Activities
    # ------------------------------------------------------------------

    def test_add_and_all_activities(self) -> None:
        a = Activity(
            title="Test Event",
            description="A test",
            category=ActivityCategory.MUSIC,
            location="Here",
            cost=10.0,
            tags=["test"],
            source="manual",
            url="https://example.com",
        )
        aid = self.db.add_activity(a, latitude=40.0, longitude=-74.0, geohash="dr5rs")
        assert aid > 0

        all_a = self.db.all_activities()
        assert len(all_a) == 1
        assert all_a[0].title == "Test Event"
        assert all_a[0].category == ActivityCategory.MUSIC
        assert all_a[0].cost == 10.0
        assert all_a[0].tags == ["test"]
        assert all_a[0].source == "manual"
        assert all_a[0].url == "https://example.com"

    def test_remove_activity(self) -> None:
        a = Activity(title="Removable", description="", category=ActivityCategory.OTHER, location="")
        self.db.add_activity(a)
        assert len(self.db.all_activities()) == 1
        assert self.db.remove_activity("Removable") is True
        assert len(self.db.all_activities()) == 0
        assert self.db.remove_activity("Nope") is False

    def test_get_activity_by_title(self) -> None:
        a = Activity(title="Unique", description="Desc", category=ActivityCategory.SPORTS, location="Loc")
        self.db.add_activity(a)
        found = self.db.get_activity_by_title("Unique")
        assert found is not None
        assert found.title == "Unique"
        assert self.db.get_activity_by_title("Nope") is None

    def test_get_activity_by_id(self) -> None:
        a = Activity(title="ByID", description="", category=ActivityCategory.OTHER, location="")
        aid = self.db.add_activity(a)
        row = self.db.get_activity_by_id(aid)
        assert row is not None
        assert row["title"] == "ByID"
        assert self.db.get_activity_by_id(999) is None

    def test_clear_activities(self) -> None:
        self.db.add_activity(Activity(title="A", description="", category=ActivityCategory.OTHER, location=""))
        self.db.add_activity(Activity(title="B", description="", category=ActivityCategory.OTHER, location=""))
        assert len(self.db.all_activities()) == 2
        self.db.clear_activities()
        assert len(self.db.all_activities()) == 0

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def test_search_by_query(self) -> None:
        self.db.add_activity(Activity(title="Yoga Class", description="Morning yoga", category=ActivityCategory.SPORTS, location="Park"))
        self.db.add_activity(Activity(title="Pottery", description="Make ceramics", category=ActivityCategory.ARTS, location="Studio"))
        results = self.db.search_activities(query="yoga")
        assert len(results) == 1
        assert results[0].title == "Yoga Class"

    def test_search_by_category(self) -> None:
        self.db.add_activity(Activity(title="A", description="", category=ActivityCategory.MUSIC, location=""))
        self.db.add_activity(Activity(title="B", description="", category=ActivityCategory.ARTS, location=""))
        results = self.db.search_activities(category="music")
        assert len(results) == 1
        assert results[0].title == "A"

    def test_search_by_max_cost(self) -> None:
        self.db.add_activity(Activity(title="Free", description="", category=ActivityCategory.OTHER, location="", cost=0))
        self.db.add_activity(Activity(title="Paid", description="", category=ActivityCategory.OTHER, location="", cost=50))
        results = self.db.search_activities(max_cost=10)
        assert len(results) == 1
        assert results[0].title == "Free"

    def test_search_by_location(self) -> None:
        self.db.add_activity(Activity(title="A", description="", category=ActivityCategory.OTHER, location="Central Park"))
        self.db.add_activity(Activity(title="B", description="", category=ActivityCategory.OTHER, location="Downtown"))
        results = self.db.search_activities(location="park")
        assert len(results) == 1
        assert results[0].title == "A"

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    def test_add_and_get_reviews(self) -> None:
        aid = self.db.add_activity(Activity(title="Reviewed", description="", category=ActivityCategory.OTHER, location=""))
        rid = self.db.add_review(aid, "Great!", rating=4.5, author="Alice", source_name="google")
        assert rid > 0

        reviews = self.db.get_reviews(aid)
        assert len(reviews) == 1
        assert reviews[0]["text"] == "Great!"
        assert reviews[0]["rating"] == 4.5
        assert reviews[0]["author"] == "Alice"

    def test_get_reviews_empty(self) -> None:
        assert self.db.get_reviews(999) == []

    # ------------------------------------------------------------------
    # Cells Fetched
    # ------------------------------------------------------------------

    def test_is_cell_fetched(self) -> None:
        assert self.db.is_cell_fetched("dr5rs", "foursquare") is False
        self.db.mark_cell_fetched("dr5rs", "foursquare")
        assert self.db.is_cell_fetched("dr5rs", "foursquare") is True
        assert self.db.is_cell_fetched("dr5rs", "yelp") is False

    def test_mark_cell_fetched_idempotent(self) -> None:
        self.db.mark_cell_fetched("abc", "src")
        assert self.db.is_cell_fetched("abc", "src") is True
        self.db.mark_cell_fetched("abc", "src")
        assert self.db.is_cell_fetched("abc", "src") is True

    def test_get_stale_cells_not_stale_after_fetch(self) -> None:
        self.db.get_or_create_source("fresh", 999999)
        self.db.mark_cell_fetched("a", "fresh")
        assert len(self.db.get_stale_cells("fresh")) == 0

    def test_get_stale_cells_with_max_age(self) -> None:
        self.db.mark_cell_fetched("x", "src")
        assert len(self.db.get_stale_cells("src", max_age_seconds=86400)) == 0

    # ------------------------------------------------------------------
    # Expired activities
    # ------------------------------------------------------------------

    def test_get_expired_activities(self) -> None:
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        future = datetime.now(timezone.utc) + timedelta(days=1)
        self.db.add_activity(Activity(title="Past", description="", category=ActivityCategory.OTHER, location="", expires_at=past))
        self.db.add_activity(Activity(title="Future", description="", category=ActivityCategory.OTHER, location="", expires_at=future))
        self.db.add_activity(Activity(title="Never", description="", category=ActivityCategory.OTHER, location=""))
        expired = self.db.get_expired_activities()
        assert len(expired) == 1
        assert expired[0].title == "Past"

    def test_remove_expired(self) -> None:
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        self.db.add_activity(Activity(title="Gone", description="", category=ActivityCategory.OTHER, location="", expires_at=past))
        self.db.add_activity(Activity(title="Stay", description="", category=ActivityCategory.OTHER, location=""))
        assert self.db.remove_expired() == 1
        assert len(self.db.all_activities()) == 1
        assert self.db.all_activities()[0].title == "Stay"

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def test_context_manager(self) -> None:
        with Database(":memory:") as d:
            d.add_activity(Activity(title="CM", description="", category=ActivityCategory.OTHER, location=""))
            assert len(d.all_activities()) == 1
