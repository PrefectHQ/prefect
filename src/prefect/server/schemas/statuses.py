from prefect.utilities.collections import AutoEnum


class WorkPoolStatus(AutoEnum):
    """Enumeration of work pool statuses."""

    READY = "READY"
    NOT_READY = "NOT_READY"
    PAUSED = "PAUSED"


class WorkerStatus(AutoEnum):
    """Enumeration of worker statuses."""

    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
