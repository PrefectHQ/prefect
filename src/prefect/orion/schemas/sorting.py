"""
Schemas for sorting Orion API objects.
"""

from sqlalchemy.sql.expression import ColumnElement

from prefect.utilities.enum import AutoEnum
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


class FlowRunSort(AutoEnum):
    """Defines flow run sorting options."""

    ID_DESC = AutoEnum.auto()
    EXPECTED_START_TIME_ASC = AutoEnum.auto()
    EXPECTED_START_TIME_DESC = AutoEnum.auto()
    NEXT_SCHEDULED_START_TIME_ASC = AutoEnum.auto()
    END_TIME_DESC = AutoEnum.auto()

    @inject_db
    def as_sql_sort(
        self,
        db: OrionDBInterface,
    ) -> ColumnElement:
        """Return an expression used to sort flow runs"""
        sort_mapping = {
            "ID_DESC": db.FlowRun.id.desc(),
            "EXPECTED_START_TIME_ASC": db.FlowRun.expected_start_time.asc(),
            "EXPECTED_START_TIME_DESC": db.FlowRun.expected_start_time.desc(),
            "NEXT_SCHEDULED_START_TIME_ASC": db.FlowRun.next_scheduled_start_time.asc(),
            "END_TIME_DESC": db.FlowRun.end_time.desc(),
        }
        return sort_mapping[self.value]


class TaskRunSort(AutoEnum):
    """Defines task run sorting options."""

    ID_DESC = AutoEnum.auto()
    EXPECTED_START_TIME_ASC = AutoEnum.auto()
    EXPECTED_START_TIME_DESC = AutoEnum.auto()
    NEXT_SCHEDULED_START_TIME_ASC = AutoEnum.auto()
    END_TIME_DESC = AutoEnum.auto()

    @inject_db
    def as_sql_sort(
        self,
        db: OrionDBInterface,
    ) -> ColumnElement:
        """Return an expression used to sort task runs"""
        sort_mapping = {
            "ID_DESC": db.TaskRun.id.desc(),
            "EXPECTED_START_TIME_ASC": db.TaskRun.expected_start_time.asc(),
            "EXPECTED_START_TIME_DESC": db.TaskRun.expected_start_time.desc(),
            "NEXT_SCHEDULED_START_TIME_ASC": db.TaskRun.next_scheduled_start_time.asc(),
            "END_TIME_DESC": db.TaskRun.end_time.desc(),
        }
        return sort_mapping[self.value]


class LogSort(AutoEnum):
    """Defines log sorting options."""

    TIMESTAMP_ASC = AutoEnum.auto()
    TIMESTAMP_DESC = AutoEnum.auto()
    LEVEL_ASC = AutoEnum.auto()
    LEVEL_DESC = AutoEnum.auto()
    FLOW_RUN_ID_ASC = AutoEnum.auto()
    FLOW_RUN_ID_DESC = AutoEnum.auto()
    TASK_RUN_ID_ASC = AutoEnum.auto()
    TASK_RUN_ID_DESC = AutoEnum.auto()

    @inject_db
    def as_sql_sort(
        self,
        db: OrionDBInterface,
    ) -> ColumnElement:
        """Return an expression used to sort task runs"""
        sort_mapping = {
            "TIMESTAMP_ASC": db.Log.timestamp.asc(),
            "TIMESTAMP_DESC": db.Log.timestamp.desc(),
            "LEVEL_ASC": db.Log.level.asc(),
            "LEVEL_DESC": db.Log.level.desc(),
            "FLOW_RUN_ID_ASC": db.Log.flow_run_id.asc(),
            "FLOW_RUN_ID_DESC": db.Log.flow_run_id.desc(),
            "TASK_RUN_ID_ASC": db.Log.task_run_id.asc(),
            "TASK_RUN_ID_DESC": db.Log.task_run_id.desc(),
        }
        return sort_mapping[self.value]
