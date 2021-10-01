"""
Schemas for sorting Orion API objects.
"""

from sqlalchemy.sql.expression import ColumnElement

from prefect.orion import models
from prefect.orion.utilities.enum import AutoEnum


class FlowRunSort(AutoEnum):
    """Defines flow run sorting options"""

    ID_DESC = AutoEnum.auto()
    EXPECTED_START_TIME_DESC = AutoEnum.auto()
    NEXT_SCHEDULED_START_TIME_ASC = AutoEnum.auto()

    def as_sql_sort(self) -> ColumnElement:
        """Return an expression used to sort flow runs"""
        sort_mapping = {
            "ID_DESC": models.orm.FlowRun.id.desc(),
            "EXPECTED_START_TIME_DESC": models.orm.FlowRun.expected_start_time.desc(),
            "NEXT_SCHEDULED_START_TIME_ASC": models.orm.FlowRun.next_scheduled_start_time.asc(),
        }
        return sort_mapping[self.value]


class TaskRunSort(AutoEnum):
    """Defines task run sorting options"""

    ID_DESC = AutoEnum.auto()
    EXPECTED_START_TIME_DESC = AutoEnum.auto()
    NEXT_SCHEDULED_START_TIME_ASC = AutoEnum.auto()

    def as_sql_sort(self) -> ColumnElement:
        """Return an expression used to sort task runs"""
        sort_mapping = {
            "ID_DESC": models.orm.TaskRun.id.desc(),
            "EXPECTED_START_TIME_DESC": models.orm.TaskRun.expected_start_time.desc(),
            "NEXT_SCHEDULED_START_TIME_ASC": models.orm.TaskRun.next_scheduled_start_time.asc(),
        }
        return sort_mapping[self.value]
