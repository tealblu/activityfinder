from activityfinder.indexer import Indexer
from activityfinder.models import Activity, SearchCriteria


class Recommender:
    def __init__(self, indexer: Indexer) -> None:
        self._indexer = indexer

    def search(self, criteria: SearchCriteria) -> list[Activity]:
        results = self._indexer.all()
        if criteria.query:
            q = criteria.query.lower()
            results = [
                a
                for a in results
                if q in a.title.lower() or q in a.description.lower()
            ]
        if criteria.categories:
            results = [a for a in results if a.category in criteria.categories]
        if criteria.max_cost is not None:
            results = [a for a in results if a.cost <= criteria.max_cost]
        if criteria.location:
            loc = criteria.location.lower()
            results = [a for a in results if loc in a.location.lower()]
        if criteria.tags:
            results = [
                a for a in results if any(t in a.tags for t in criteria.tags)
            ]
        return results
