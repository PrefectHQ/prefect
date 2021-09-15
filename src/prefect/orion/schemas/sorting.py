from prefect.orion import models
from prefect.orion.utilities.enum import AutoEnum


class FlowRunSort(AutoEnum):
    ID_DESC = AutoEnum.auto()
    EXPECTED_START_TIME_DESC = AutoEnum.auto()
    NEXT_SCHEDULED_START_TIME_ASC = AutoEnum.auto()

    def as_sql_sort(self):
        sort_mapping = {
            "ID_DESC": models.orm.FlowRun.id.desc(),
            "EXPECTED_START_TIME_DESC": models.orm.FlowRun.expected_start_time.desc(),
            "NEXT_SCHEDULED_START_TIME_ASC": models.orm.FlowRun.next_scheduled_start_time.asc(),
        }
        return sort_mapping[self.value]


class TaskRunSort(AutoEnum):
    ID_DESC = AutoEnum.auto()
    EXPECTED_START_TIME_DESC = AutoEnum.auto()
    NEXT_SCHEDULED_START_TIME_ASC = AutoEnum.auto()

    def as_sql_sort(self):
        sort_mapping = {
            "ID_DESC": models.orm.TaskRun.id.desc(),
            "EXPECTED_START_TIME_DESC": models.orm.TaskRun.expected_start_time.desc(),
            "NEXT_SCHEDULED_START_TIME_ASC": models.orm.TaskRun.next_scheduled_start_time.asc(),
        }
        return sort_mapping[self.value]
