import datetime

from prefect.core.task import Task
from prefect.client.secrets import Secret as _Secret
from prefect.engine.result_handlers import SecretResultHandler


class Secret(Task):
    """
    Base Prefect Secrets Task.  This task retrieves the underlying secret through
    the Prefect Secrets API (which has the ability to toggle between local vs. Cloud secrets).
    Users should subclass this Task and override its `run` method for plugging into other Secret stores,
    as it is handled differently during execution to ensure the underlying secret value is not accidentally
    persisted in a non-safe location.

    Args:
        - name (str): The name of the underlying secret
        - **kwargs (Any, optional): additional keyword arguments to pass to the Task constructor
    """

    def __init__(self, name, **kwargs):
        kwargs["name"] = name
        kwargs.setdefault("max_retries", 2)
        kwargs.setdefault("retry_delay", datetime.timedelta(seconds=1))
        kwargs["result_handler"] = SecretResultHandler(secret_task=self)
        super().__init__(**kwargs)

    def run(self):
        return _Secret(self.name).get()
