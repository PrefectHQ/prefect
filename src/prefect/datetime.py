from datetime import datetime

from zoneinfo import ZoneInfo


def now(name: str = "UTC") -> datetime:
    return datetime.now(ZoneInfo(name))
