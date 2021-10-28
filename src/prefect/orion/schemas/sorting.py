"""
Schemas for sorting Orion API objects.
"""

from sqlalchemy.sql.expression import ColumnElement

from prefect.orion.utilities.enum import AutoEnum
from prefect.orion.database.dependencies import inject_db_config


class FlowRunSort(AutoEnum):
    """Defines flow run sorting options."""

    ID_DESC = AutoEnum.auto()
    EXPECTED_START_TIME_ASC = AutoEnum.auto()
    EXPECTED_START_TIME_DESC = AutoEnum.auto()
    NEXT_SCHEDULED_START_TIME_ASC = AutoEnum.auto()
    END_TIME_DESC = AutoEnum.auto()

    @inject_db_config
    async def as_sql_sort(self, db_config=None) -> ColumnElement:
        """Return an expression used to sort flow runs"""
        sort_mapping = {
            "ID_DESC": db_config.FlowRun.id.desc(),
            "EXPECTED_START_TIME_ASC": db_config.FlowRun.expected_start_time.asc(),
            "EXPECTED_START_TIME_DESC": db_config.FlowRun.expected_start_time.desc(),
            "NEXT_SCHEDULED_START_TIME_ASC": db_config.FlowRun.next_scheduled_start_time.asc(),
            "END_TIME_DESC": db_config.FlowRun.end_time.desc(),
        }
        return sort_mapping[self.value]


class TaskRunSort(AutoEnum):
    """Defines task run sorting options."""

    ID_DESC = AutoEnum.auto()
    EXPECTED_START_TIME_ASC = AutoEnum.auto()
    EXPECTED_START_TIME_DESC = AutoEnum.auto()
    NEXT_SCHEDULED_START_TIME_ASC = AutoEnum.auto()
    END_TIME_DESC = AutoEnum.auto()

    @inject_db_config
    async def as_sql_sort(self, db_config=None) -> ColumnElement:
        """Return an expression used to sort task runs"""
        sort_mapping = {
            "ID_DESC": db_config.TaskRun.id.desc(),
            "EXPECTED_START_TIME_ASC": db_config.TaskRun.expected_start_time.asc(),
            "EXPECTED_START_TIME_DESC": db_config.TaskRun.expected_start_time.desc(),
            "NEXT_SCHEDULED_START_TIME_ASC": db_config.TaskRun.next_scheduled_start_time.asc(),
            "END_TIME_DESC": db_config.TaskRun.end_time.desc(),
        }
        return sort_mapping[self.value]
