"""
Schemas for sorting Orion API objects.
"""

from sqlalchemy.sql.expression import ColumnElement

from prefect.orion.utilities.enum import AutoEnum
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
