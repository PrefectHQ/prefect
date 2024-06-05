"""
Schemas for sorting Prefect REST API objects.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa

from prefect.server.database import orm_models
from prefect.utilities.collections import AutoEnum

if TYPE_CHECKING:
    from sqlalchemy.sql.expression import ColumnElement

# TODO: Consider moving the `as_sql_sort` functions out of here since they are a
#       database model level function and do not properly separate concerns when
#       present in the schemas module


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

    def as_sql_sort(self) -> "ColumnElement":
        from sqlalchemy.sql.functions import coalesce

        """Return an expression used to sort flow runs"""
        sort_mapping = {
            "ID_DESC": orm_models.FlowRun.id.desc(),
            "START_TIME_ASC": coalesce(
                orm_models.FlowRun.start_time, orm_models.FlowRun.expected_start_time
            ).asc(),
            "START_TIME_DESC": coalesce(
                orm_models.FlowRun.start_time, orm_models.FlowRun.expected_start_time
            ).desc(),
            "EXPECTED_START_TIME_ASC": orm_models.FlowRun.expected_start_time.asc(),
            "EXPECTED_START_TIME_DESC": orm_models.FlowRun.expected_start_time.desc(),
            "NAME_ASC": orm_models.FlowRun.name.asc(),
            "NAME_DESC": orm_models.FlowRun.name.desc(),
            "NEXT_SCHEDULED_START_TIME_ASC": orm_models.FlowRun.next_scheduled_start_time.asc(),
            "END_TIME_DESC": orm_models.FlowRun.end_time.desc(),
        }
        return sort_mapping[self.value]


class TaskRunSort(AutoEnum):
    """Defines task run sorting options."""

    ID_DESC = AutoEnum.auto()
    EXPECTED_START_TIME_ASC = AutoEnum.auto()
    EXPECTED_START_TIME_DESC = AutoEnum.auto()
    NAME_ASC = AutoEnum.auto()
    NAME_DESC = AutoEnum.auto()
    NEXT_SCHEDULED_START_TIME_ASC = AutoEnum.auto()
    END_TIME_DESC = AutoEnum.auto()

    def as_sql_sort(self) -> "ColumnElement":
        """Return an expression used to sort task runs"""
        sort_mapping = {
            "ID_DESC": orm_models.TaskRun.id.desc(),
            "EXPECTED_START_TIME_ASC": orm_models.TaskRun.expected_start_time.asc(),
            "EXPECTED_START_TIME_DESC": orm_models.TaskRun.expected_start_time.desc(),
            "NAME_ASC": orm_models.TaskRun.name.asc(),
            "NAME_DESC": orm_models.TaskRun.name.desc(),
            "NEXT_SCHEDULED_START_TIME_ASC": orm_models.TaskRun.next_scheduled_start_time.asc(),
            "END_TIME_DESC": orm_models.TaskRun.end_time.desc(),
        }
        return sort_mapping[self.value]


class LogSort(AutoEnum):
    """Defines log sorting options."""

    TIMESTAMP_ASC = AutoEnum.auto()
    TIMESTAMP_DESC = AutoEnum.auto()

    def as_sql_sort(self) -> "ColumnElement":
        """Return an expression used to sort task runs"""
        sort_mapping = {
            "TIMESTAMP_ASC": orm_models.Log.timestamp.asc(),
            "TIMESTAMP_DESC": orm_models.Log.timestamp.desc(),
        }
        return sort_mapping[self.value]


class FlowSort(AutoEnum):
    """Defines flow sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    NAME_ASC = AutoEnum.auto()
    NAME_DESC = AutoEnum.auto()

    def as_sql_sort(self) -> "ColumnElement":
        """Return an expression used to sort flows"""
        sort_mapping = {
            "CREATED_DESC": orm_models.Flow.created.desc(),
            "UPDATED_DESC": orm_models.Flow.updated.desc(),
            "NAME_ASC": orm_models.Flow.name.asc(),
            "NAME_DESC": orm_models.Flow.name.desc(),
        }
        return sort_mapping[self.value]


class DeploymentSort(AutoEnum):
    """Defines deployment sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    NAME_ASC = AutoEnum.auto()
    NAME_DESC = AutoEnum.auto()

    def as_sql_sort(self) -> "ColumnElement":
        """Return an expression used to sort deployments"""
        sort_mapping = {
            "CREATED_DESC": orm_models.Deployment.created.desc(),
            "UPDATED_DESC": orm_models.Deployment.updated.desc(),
            "NAME_ASC": orm_models.Deployment.name.asc(),
            "NAME_DESC": orm_models.Deployment.name.desc(),
        }
        return sort_mapping[self.value]


class ArtifactSort(AutoEnum):
    """Defines artifact sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    ID_DESC = AutoEnum.auto()
    KEY_DESC = AutoEnum.auto()
    KEY_ASC = AutoEnum.auto()

    def as_sql_sort(self) -> "ColumnElement":
        """Return an expression used to sort artifacts"""
        sort_mapping = {
            "CREATED_DESC": orm_models.Artifact.created.desc(),
            "UPDATED_DESC": orm_models.Artifact.updated.desc(),
            "ID_DESC": orm_models.Artifact.id.desc(),
            "KEY_DESC": orm_models.Artifact.key.desc(),
            "KEY_ASC": orm_models.Artifact.key.asc(),
        }
        return sort_mapping[self.value]


class ArtifactCollectionSort(AutoEnum):
    """Defines artifact collection sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    ID_DESC = AutoEnum.auto()
    KEY_DESC = AutoEnum.auto()
    KEY_ASC = AutoEnum.auto()

    def as_sql_sort(self) -> "ColumnElement":
        """Return an expression used to sort artifact collections"""
        sort_mapping = {
            "CREATED_DESC": orm_models.ArtifactCollection.created.desc(),
            "UPDATED_DESC": orm_models.ArtifactCollection.updated.desc(),
            "ID_DESC": orm_models.ArtifactCollection.id.desc(),
            "KEY_DESC": orm_models.ArtifactCollection.key.desc(),
            "KEY_ASC": orm_models.ArtifactCollection.key.asc(),
        }
        return sort_mapping[self.value]


class VariableSort(AutoEnum):
    """Defines variables sorting options."""

    CREATED_DESC = "CREATED_DESC"
    UPDATED_DESC = "UPDATED_DESC"
    NAME_DESC = "NAME_DESC"
    NAME_ASC = "NAME_ASC"

    def as_sql_sort(self) -> "ColumnElement":
        """Return an expression used to sort variables"""
        sort_mapping = {
            "CREATED_DESC": orm_models.Variable.created.desc(),
            "UPDATED_DESC": orm_models.Variable.updated.desc(),
            "NAME_DESC": orm_models.Variable.name.desc(),
            "NAME_ASC": orm_models.Variable.name.asc(),
        }
        return sort_mapping[self.value]


class BlockDocumentSort(AutoEnum):
    """Defines block document sorting options."""

    NAME_DESC = "NAME_DESC"
    NAME_ASC = "NAME_ASC"
    BLOCK_TYPE_AND_NAME_ASC = "BLOCK_TYPE_AND_NAME_ASC"

    def as_sql_sort(self) -> "ColumnElement":
        """Return an expression used to sort block documents"""
        sort_mapping = {
            "NAME_DESC": orm_models.BlockDocument.name.desc(),
            "NAME_ASC": orm_models.BlockDocument.name.asc(),
            "BLOCK_TYPE_AND_NAME_ASC": sa.text("block_type_name asc, name asc"),
        }
        return sort_mapping[self.value]
