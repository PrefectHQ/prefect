from prefect.utilities.collections import AutoEnum


class AutomationSort(AutoEnum):
    """Defines automation sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    NAME_ASC = AutoEnum.auto()
    NAME_DESC = AutoEnum.auto()
