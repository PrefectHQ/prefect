import prefect
from prefect import Task
from prefect.tasks.core import FunctionTask


def approval(upstream_task, notification_task, success_branch, fail_branch):
    pass


class RequestApproval(Task):

    def __init__(self, next_task_name, **kwargs):
        self.next_task_name = next_task_name
        super().__init__(**kwargs)

    def run(self, result=None):
        return result

class WaitForApproval(Task):

    def __init__(self, **kwargs):
        super().__init__(trigger=prefect.triggers.manual_only, **kwargs)

    def run(self, approved=True):
        return approved
