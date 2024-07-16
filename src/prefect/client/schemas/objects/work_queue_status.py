from prefect.utilities.collections import AutoEnum


class WorkQueueStatus(AutoEnum):
    """Enumeration of work queue statuses."""

    READY = AutoEnum.auto()
    NOT_READY = AutoEnum.auto()
    PAUSED = AutoEnum.auto()
