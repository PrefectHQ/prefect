from prefect.core.task import Task
from prefect.client.secrets import Secret as _Secret


class Secret(Task):
    """
    Base Secrets class.
    """

    def __init__(self, name, **kwargs):
        kwargs["name"] = name
        super().__init__(**kwargs)

    def run(self):
        return _Secret(self.name).get()
