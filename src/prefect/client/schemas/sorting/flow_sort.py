from prefect.utilities.collections import AutoEnum


class FlowSort(AutoEnum):
    """Defines flow sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    NAME_ASC = AutoEnum.auto()
    NAME_DESC = AutoEnum.auto()
