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

    Raises:
        - ValueError: if a `result_handler` keyword is passed
    """

    def __init__(self, name, **kwargs):
        kwargs["name"] = name
        kwargs.setdefault("max_retries", 2)
        kwargs.setdefault("retry_delay", datetime.timedelta(seconds=1))
        if kwargs.get("result_handler"):
            raise ValueError("Result Handlers for Secrets are not configurable.")
        kwargs["result_handler"] = SecretResultHandler(secret_task=self)
        super().__init__(**kwargs)

    def run(self):
        """
        The run method for Secret Tasks.  This method actually retrieves and returns the underlying secret value
        using the `Secret.get()` method.  Note that this method first checks context for the secret value, and if not
        found either raises an error or queries Prefect Cloud, depending on whether `config.cloud.use_local_secrets`
        is `True` or `False`.

        Returns:
            - Any: the underlying value of the Prefect Secret
        """
        return _Secret(self.name).get()
