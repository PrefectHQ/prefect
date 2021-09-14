from prefect.orion import models
from prefect.orion.utilities.enum import AutoEnum


class FlowRunSort(AutoEnum):
    id_desc = AutoEnum.auto()
    expected_start_time_desc = AutoEnum.auto()
    next_scheduled_start_time_asc = AutoEnum.auto()

    def as_sql_sort(self):
        sort_mapping = {
            "id_desc": models.orm.FlowRun.id.desc(),
            "expected_start_time_desc": models.orm.FlowRun.expected_start_time.desc(),
            "next_scheduled_start_time_asc": models.orm.FlowRun.next_scheduled_start_time.asc(),
        }
        return sort_mapping[self.value]


class TaskRunSort(AutoEnum):
    id_desc = AutoEnum.auto()
    expected_start_time_desc = AutoEnum.auto()
    next_scheduled_start_time_asc = AutoEnum.auto()

    def as_sql_sort(self):
        sort_mapping = {
            "id_desc": models.orm.TaskRun.id.desc(),
            "expected_start_time_desc": models.orm.TaskRun.expected_start_time.desc(),
            "next_scheduled_start_time_asc": models.orm.TaskRun.next_scheduled_start_time.asc(),
        }
        return sort_mapping[self.value]
