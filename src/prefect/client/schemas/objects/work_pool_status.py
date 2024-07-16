from prefect.utilities.collections import AutoEnum


class WorkPoolStatus(AutoEnum):
    """Enumeration of work pool statuses."""

    READY = AutoEnum.auto()
    NOT_READY = AutoEnum.auto()
    PAUSED = AutoEnum.auto()

    @property
    def display_name(self):
        return self.name.replace("_", " ").capitalize()