from prefect.utilities.collections import AutoEnum


class ArtifactSort(AutoEnum):
    """Defines artifact sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    ID_DESC = AutoEnum.auto()
    KEY_DESC = AutoEnum.auto()
    KEY_ASC = AutoEnum.auto()
