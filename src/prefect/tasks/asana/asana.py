import json
from typing import Any, List

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs

try:
    import asana
except ImportError:
    pass



class OpenAsanaToDo(Task):
    """
    Task for opening / creating new Asana tasks using the Asana REST API.

    Args:
        - data (dict, optional): full coinfigured data object to include in the task.  See https://developers.asana.com/docs/create-a-task for more information.  If a data object is included, other inputs will be ignored; can also be provided to the
            `run` method 
        - project (str; , required): The GID of the project the task will be posted to; can also be provided to the
            `run` method 
        - name (str, optional): the name of the task to create; can also be provided to the
            `run` method
        - notes (str, optional): the contents of the task; can also be provided to the `run` method
        - token (str): an Asana Personal Access Token
        - **kwargs (Any, optional): additional keyword arguments to pass to the standard Task
            init method
    """

    def __init__(
        self,
        data: str = None,
        name: str = None,
        notes: str = None,
        **kwargs: Any
    ):
        self.data = data
        self.name = name
        self.notes = notes
        super().__init__(**kwargs)

    @defaults_from_attrs("data", "name", "notes", "followers")
    def run(
        self,
        data: str = None,
        name: str = None,
        notes: str = None,
        followers: List[str] = None,
        token: str = None,
    ) -> None:
        """
        Run method for this Task. Invoked by calling this Task after initialization within a
        Flow context, or by using `Task.bind`.

        Args:
        - data (dict, optional): full coinfigured data object to include in the task.  See https://developers.asana.com/docs/create-a-task for more information.  If a data object is included, other inputs will be ignored; can also be provided at initialization
        - name (str, optional): the name of the task to create; can also be provided at initialization
        - notes (str, optional): the contents of the task; can also be provided at initialization
        - token (str): an ASANA Personal Access Token

        Raises:
            - ValueError: if no project is provided
            - ValueError: if no access token is provided
            - ValueError: if no result is returned

        Returns:
            - None
        """
        if project is None:
            raise ValueError("An Asana project must be provided.")

        if token is None:
            raise ValueError("An Asana access token must be provided.")

        # 'import requests' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import requests

        client = asana.Client.access_token(token)

        if data:
            result = client.tasks.create_task({
            'data': data
        })

        else: 
            result = client.tasks.create_task({
                'name': name,
                'notes': notes,
                'projects': [
                    project
                ]
            })

        if not result:
            raise ValueError("Creating Asana Task failed")
