"""
Schemas for sorting Prefect REST API objects.
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from prefect.server.utilities.database import db_injector
from prefect.utilities.collections import AutoEnum

if TYPE_CHECKING:
    from prefect.server.database import PrefectDBInterface

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

    @db_injector
    def as_sql_sort(self, db: "PrefectDBInterface") -> Iterable[sa.ColumnElement[Any]]:
        """Return an expression used to sort flow runs"""
        sort_mapping: dict[str, Iterable[sa.ColumnElement[Any]]] = {
            "ID_DESC": [db.FlowRun.id.desc()],
            "START_TIME_ASC": [
                sa.func.coalesce(
                    db.FlowRun.start_time, db.FlowRun.expected_start_time
                ).asc()
            ],
            "START_TIME_DESC": [
                sa.func.coalesce(
                    db.FlowRun.start_time, db.FlowRun.expected_start_time
                ).desc()
            ],
            "EXPECTED_START_TIME_ASC": [db.FlowRun.expected_start_time.asc()],
            "EXPECTED_START_TIME_DESC": [db.FlowRun.expected_start_time.desc()],
            "NAME_ASC": [db.FlowRun.name.asc()],
            "NAME_DESC": [db.FlowRun.name.desc()],
            "NEXT_SCHEDULED_START_TIME_ASC": [
                db.FlowRun.next_scheduled_start_time.asc()
            ],
            "END_TIME_DESC": [db.FlowRun.end_time.desc()],
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

    @db_injector
    def as_sql_sort(self, db: "PrefectDBInterface") -> Iterable[sa.ColumnElement[Any]]:
        """Return an expression used to sort task runs"""
        sort_mapping: dict[str, Iterable[sa.ColumnElement[Any]]] = {
            "ID_DESC": [db.TaskRun.id.desc()],
            "EXPECTED_START_TIME_ASC": [db.TaskRun.expected_start_time.asc()],
            "EXPECTED_START_TIME_DESC": [db.TaskRun.expected_start_time.desc()],
            "NAME_ASC": [db.TaskRun.name.asc()],
            "NAME_DESC": [db.TaskRun.name.desc()],
            "NEXT_SCHEDULED_START_TIME_ASC": [
                db.TaskRun.next_scheduled_start_time.asc()
            ],
            "END_TIME_DESC": [db.TaskRun.end_time.desc()],
        }
        return sort_mapping[self.value]


class LogSort(AutoEnum):
    """Defines log sorting options."""

    TIMESTAMP_ASC = AutoEnum.auto()
    TIMESTAMP_DESC = AutoEnum.auto()

    @db_injector
    def as_sql_sort(self, db: "PrefectDBInterface") -> Iterable[sa.ColumnElement[Any]]:
        """Return an expression used to sort task runs"""
        sort_mapping: dict[str, Iterable[sa.ColumnElement[Any]]] = {
            "TIMESTAMP_ASC": [db.Log.timestamp.asc()],
            "TIMESTAMP_DESC": [db.Log.timestamp.desc()],
        }
        return sort_mapping[self.value]


class FlowSort(AutoEnum):
    """Defines flow sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    NAME_ASC = AutoEnum.auto()
    NAME_DESC = AutoEnum.auto()

    @db_injector
    def as_sql_sort(self, db: "PrefectDBInterface") -> Iterable[sa.ColumnElement[Any]]:
        """Return an expression used to sort task runs"""
        sort_mapping: dict[str, Iterable[sa.ColumnElement[Any]]] = {
            "CREATED_DESC": [db.Flow.created.desc()],
            "UPDATED_DESC": [db.Flow.updated.desc()],
            "NAME_ASC": [db.Flow.name.asc()],
            "NAME_DESC": [db.Flow.name.desc()],
        }
        return sort_mapping[self.value]


class DeploymentSort(AutoEnum):
    """Defines deployment sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    NAME_ASC = AutoEnum.auto()
    NAME_DESC = AutoEnum.auto()

    @db_injector
    def as_sql_sort(self, db: "PrefectDBInterface") -> Iterable[sa.ColumnElement[Any]]:
        """Return an expression used to sort task runs"""
        sort_mapping: dict[str, Iterable[sa.ColumnElement[Any]]] = {
            "CREATED_DESC": [db.Deployment.created.desc()],
            "UPDATED_DESC": [db.Deployment.updated.desc()],
            "NAME_ASC": [db.Deployment.name.asc()],
            "NAME_DESC": [db.Deployment.name.desc()],
        }
        return sort_mapping[self.value]


class ArtifactSort(AutoEnum):
    """Defines artifact sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    ID_DESC = AutoEnum.auto()
    KEY_DESC = AutoEnum.auto()
    KEY_ASC = AutoEnum.auto()

    @db_injector
    def as_sql_sort(self, db: "PrefectDBInterface") -> Iterable[sa.ColumnElement[Any]]:
        """Return an expression used to sort task runs"""
        sort_mapping: dict[str, Iterable[sa.ColumnElement[Any]]] = {
            "CREATED_DESC": [db.Artifact.created.desc()],
            "UPDATED_DESC": [db.Artifact.updated.desc()],
            "ID_DESC": [db.Artifact.id.desc()],
            "KEY_DESC": [db.Artifact.key.desc()],
            "KEY_ASC": [db.Artifact.key.asc()],
        }
        return sort_mapping[self.value]


class ArtifactCollectionSort(AutoEnum):
    """Defines artifact collection sorting options."""

    CREATED_DESC = AutoEnum.auto()
    UPDATED_DESC = AutoEnum.auto()
    ID_DESC = AutoEnum.auto()
    KEY_DESC = AutoEnum.auto()
    KEY_ASC = AutoEnum.auto()

    @db_injector
    def as_sql_sort(self, db: "PrefectDBInterface") -> Iterable[sa.ColumnElement[Any]]:
        """Return an expression used to sort task runs"""
        sort_mapping: dict[str, Iterable[sa.ColumnElement[Any]]] = {
            "CREATED_DESC": [db.ArtifactCollection.created.desc()],
            "UPDATED_DESC": [db.ArtifactCollection.updated.desc()],
            "ID_DESC": [db.ArtifactCollection.id.desc()],
            "KEY_DESC": [db.ArtifactCollection.key.desc()],
            "KEY_ASC": [db.ArtifactCollection.key.asc()],
        }
        return sort_mapping[self.value]


class VariableSort(AutoEnum):
    """Defines variables sorting options."""

    CREATED_DESC = "CREATED_DESC"
    UPDATED_DESC = "UPDATED_DESC"
    NAME_DESC = "NAME_DESC"
    NAME_ASC = "NAME_ASC"

    @db_injector
    def as_sql_sort(self, db: "PrefectDBInterface") -> Iterable[sa.ColumnElement[Any]]:
        """Return an expression used to sort task runs"""
        sort_mapping: dict[str, Iterable[sa.ColumnElement[Any]]] = {
            "CREATED_DESC": [db.Variable.created.desc()],
            "UPDATED_DESC": [db.Variable.updated.desc()],
            "NAME_DESC": [db.Variable.name.desc()],
            "NAME_ASC": [db.Variable.name.asc()],
        }
        return sort_mapping[self.value]


class BlockDocumentSort(AutoEnum):
    """Defines block document sorting options."""

    NAME_DESC = "NAME_DESC"
    NAME_ASC = "NAME_ASC"
    BLOCK_TYPE_AND_NAME_ASC = "BLOCK_TYPE_AND_NAME_ASC"

    @db_injector
    def as_sql_sort(self, db: "PrefectDBInterface") -> Iterable[sa.ColumnElement[Any]]:
        """Return an expression used to sort task runs"""
        sort_mapping: dict[str, Iterable[sa.ColumnElement[Any]]] = {
            "NAME_DESC": [db.BlockDocument.name.desc()],
            "NAME_ASC": [db.BlockDocument.name.asc()],
            "BLOCK_TYPE_AND_NAME_ASC": [
                db.BlockDocument.block_type_name.asc(),
                db.BlockDocument.name.asc(),
            ],
        }
        return sort_mapping[self.value]
