from prefect.utilities.collections import AutoEnum


class FlowRunSort(AutoEnum):
    """Defines flow run sorting options."""

    ID_DESC = AutoEnum.auto()
    START_TIME_ASC = AutoEnum.auto()
    START_TIME_DESC = AutoEnum.auto()
    EXPECTED_START_TIME_ASC = AutoEnum.auto()
    EXPECTED_START_TIME_DESC = AutoEnum.auto()
    NAME_ASC = AutoEnum.auto()
    NAME_DESC = AutoEnum.auto()
    NEXT_SCHEDULED_START_TIME_ASC = AutoEnum.auto()
    END_TIME_DESC = AutoEnum.auto()


class TaskRunSort(AutoEnum):
    """Defines task run sorting options."""

    ID_DESC = AutoEnum.auto()
    EXPECTED_START_TIME_ASC = AutoEnum.auto()
    EXPECTED_START_TIME_DESC = AutoEnum.auto()
    NAME_ASC = AutoEnum.auto()
    NAME_DESC = AutoEnum.auto()
    NEXT_SCHEDULED_START_TIME_ASC = AutoEnum.auto()
    END_TIME_DESC = AutoEnum.auto()


class AutomationSort(AutoEnum):
    """Defines automation sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    NAME_ASC = AutoEnum.auto()
    NAME_DESC = AutoEnum.auto()


class LogSort(AutoEnum):
    """Defines log sorting options."""

    TIMESTAMP_ASC = AutoEnum.auto()
    TIMESTAMP_DESC = AutoEnum.auto()


class FlowSort(AutoEnum):
    """Defines flow sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    NAME_ASC = AutoEnum.auto()
    NAME_DESC = AutoEnum.auto()


class DeploymentSort(AutoEnum):
    """Defines deployment sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    NAME_ASC = AutoEnum.auto()
    NAME_DESC = AutoEnum.auto()
    CONCURRENCY_LIMIT_ASC = AutoEnum.auto()
    CONCURRENCY_LIMIT_DESC = AutoEnum.auto()


class ArtifactSort(AutoEnum):
    """Defines artifact sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    ID_DESC = AutoEnum.auto()
    KEY_DESC = AutoEnum.auto()
    KEY_ASC = AutoEnum.auto()


class ArtifactCollectionSort(AutoEnum):
    """Defines artifact collection sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    ID_DESC = AutoEnum.auto()
    KEY_DESC = AutoEnum.auto()
    KEY_ASC = AutoEnum.auto()


class VariableSort(AutoEnum):
    """Defines variables sorting options."""

    CREATED_DESC = "CREATED_DESC"
    UPDATED_DESC = "UPDATED_DESC"
    NAME_DESC = "NAME_DESC"
    NAME_ASC = "NAME_ASC"


class BlockDocumentSort(AutoEnum):
    """Defines block document sorting options."""

    NAME_DESC = AutoEnum.auto()
    NAME_ASC = AutoEnum.auto()
    BLOCK_TYPE_AND_NAME_ASC = AutoEnum.auto()
