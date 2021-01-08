from prefect import Task
from typing import Any
from prefect.utilities.tasks import defaults_from_attrs

try:
    import asana
except ImportError:
    pass


class OpenAsanaToDo(Task):
    """
    Task for opening / creating new Asana tasks using the Asana REST API.

    Args:
        - project (str; , required): The GID of the project the task will be posted to;
            can also be provided to the `run` method
        - name (str, optional): the name of the task to create; can also be provided to the
            `run` method
        - notes (str, optional): the contents of the task; can also be provided to the `run` method
        - token (str): an Asana Personal Access Token
        - **kwargs (Any, optional): additional keyword arguments to pass to the standard Task
            init method
    """

    def __init__(
        self,
        name: str = None,
        notes: str = None,
        project: str = None,
        token: str = None,
        **kwargs: Any
    ):
        self.name = name
        self.notes = notes
        self.project = project
        self.token = token
        super().__init__(**kwargs)

    @defaults_from_attrs("name", "notes", "project", "token")
    def run(
        self,
        name: str = None,
        notes: str = None,
        project: str = None,
        token: str = None,
    ) -> None:
        """
        Run method for this Task. Invoked by calling this Task after initialization within a
        Flow context, or by using `Task.bind`.

        Args:
        - name (str, optional): the name of the task to create; can also be provided at initialization
        - project (str; , required): The GID of the project the task will be posted to;
            can also be provided at initialization
        - notes (str, optional): the contents of the task; can also be provided at initialization
        - token (str): an ASANA Personal Access Token

        Raises:
            - ValueError: if no project is provided
            - ValueError: if no access token is provided
            - ValueError: if no result is returned

        Returns:
            - The result object with details of the new asana task
        """

        if project is None:
            raise ValueError("An Asana project must be provided.")

        if token is None:
            raise ValueError("An Asana access token must be provided.")

        client = asana.Client.access_token(token)

        result = client.tasks.create_task(
            {"name": name, "notes": notes, "projects": [project]}
        )

        if not result:
            raise ValueError("Creating Asana Task failed")

        return result
