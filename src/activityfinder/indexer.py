from activityfinder.models import Activity


class Indexer:
    def __init__(self) -> None:
        self._activities: list[Activity] = []

    def index(self, activity: Activity) -> None:
        self._activities.append(activity)

    def index_many(self, activities: list[Activity]) -> None:
        self._activities.extend(activities)

    def remove(self, title: str) -> bool:
        for i, a in enumerate(self._activities):
            if a.title == title:
                del self._activities[i]
                return True
        return False

    def all(self) -> list[Activity]:
        return list(self._activities)

    def clear(self) -> None:
        self._activities.clear()

    def __len__(self) -> int:
        return len(self._activities)
