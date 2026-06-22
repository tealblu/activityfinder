from activityfinder.indexer import Indexer
from activityfinder.models import Activity, ActivityCategory


class TestIndexer:
    def test_index_and_all(self) -> None:
        idx = Indexer()
        a = Activity(
            title="Test",
            description="Desc",
            category=ActivityCategory.OTHER,
            location="Here",
        )
        idx.index(a)
        assert idx.all() == [a]
        assert len(idx) == 1

    def test_index_many(self) -> None:
        idx = Indexer()
        acts = [
            Activity(title="A", description="", category=ActivityCategory.OTHER, location=""),
            Activity(title="B", description="", category=ActivityCategory.OTHER, location=""),
        ]
        idx.index_many(acts)
        assert len(idx) == 2

    def test_remove(self) -> None:
        idx = Indexer()
        a = Activity(
            title="Test",
            description="Desc",
            category=ActivityCategory.OTHER,
            location="Here",
        )
        idx.index(a)
        assert idx.remove("Test") is True
        assert len(idx) == 0
        assert idx.remove("Nope") is False

    def test_clear(self) -> None:
        idx = Indexer()
        idx.index(Activity(title="A", description="", category=ActivityCategory.OTHER, location=""))
        idx.clear()
        assert len(idx) == 0
