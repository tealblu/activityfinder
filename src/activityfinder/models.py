from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ActivityCategory(str, Enum):
    SPORTS = "sports"
    ARTS = "arts"
    MUSIC = "music"
    FOOD = "food"
    OUTDOORS = "outdoors"
    EDUCATION = "education"
    SOCIAL = "social"
    ENTERTAINMENT = "entertainment"
    OTHER = "other"


@dataclass
class Activity:
    title: str
    description: str
    category: ActivityCategory
    location: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    cost: float = 0.0
    tags: list[str] = field(default_factory=list)
    source: str = ""
    url: str = ""


@dataclass
class SearchCriteria:
    query: str = ""
    categories: list[ActivityCategory] = field(default_factory=list)
    max_cost: Optional[float] = None
    location: Optional[str] = None
    tags: list[str] = field(default_factory=list)
