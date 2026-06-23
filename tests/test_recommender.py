from activityfinder.db import Database
from activityfinder.indexer import Indexer
from activityfinder.models import Activity, ActivityCategory, SearchCriteria
from activityfinder.recommender import Recommender


class TestRecommender:
    def setup_method(self) -> None:
        self.db = Database(":memory:")
        self.idx = Indexer(self.db)
        self.idx.index_many(
            [
                Activity(
                    title="Yoga in the Park",
                    description="Morning yoga session",
                    category=ActivityCategory.SPORTS,
                    location="Central Park",
                    cost=0,
                    tags=["yoga", "morning"],
                ),
                Activity(
                    title="Pottery Workshop",
                    description="Learn to make ceramics",
                    category=ActivityCategory.ARTS,
                    location="Downtown Studio",
                    cost=25.0,
                    tags=["pottery", "workshop"],
                ),
                Activity(
                    title="Jazz Night",
                    description="Live jazz music",
                    category=ActivityCategory.MUSIC,
                    location="Blue Note",
                    cost=15.0,
                    tags=["jazz", "music"],
                ),
            ]
        )
        self.r = Recommender(self.idx)

    def test_search_all(self) -> None:
        results = self.r.search(SearchCriteria())
        assert len(results) == 3

    def test_search_by_query(self) -> None:
        results = self.r.search(SearchCriteria(query="yoga"))
        assert len(results) == 1
        assert results[0].title == "Yoga in the Park"

    def test_search_by_category(self) -> None:
        results = self.r.search(
            SearchCriteria(categories=[ActivityCategory.ARTS])
        )
        assert len(results) == 1
        assert results[0].title == "Pottery Workshop"

    def test_search_by_max_cost(self) -> None:
        results = self.r.search(SearchCriteria(max_cost=0))
        assert len(results) == 1
        assert results[0].title == "Yoga in the Park"

    def test_search_by_location(self) -> None:
        results = self.r.search(SearchCriteria(location="park"))
        assert len(results) == 1

    def test_search_by_tags(self) -> None:
        results = self.r.search(SearchCriteria(tags=["jazz"]))
        assert len(results) == 1
