from activityfinder.db import Database
from activityfinder.models import Activity


class Indexer:
    def __init__(self, db: Database) -> None:
        self._activities: list[Activity] = db.all_activities()
        self._db = db

    def index(self, activity: Activity) -> None:
        self._activities.append(activity)
        self._db.add_activity(activity)

    def index_many(self, activities: list[Activity]) -> None:
        self._activities.extend(activities)
        for a in activities:
            self._db.add_activity(a)

    def remove(self, title: str) -> bool:
        for i, a in enumerate(self._activities):
            if a.title == title:
                del self._activities[i]
                self._db.remove_activity(title)
                return True
        return False

    def all(self) -> list[Activity]:
        return list(self._activities)

    def clear(self) -> None:
        self._activities.clear()
        self._db.clear_activities()

    def __len__(self) -> int:
        return len(self._activities)
