from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs
from typing import Any

try:
    from jira import JIRA
except ImportError:
    pass


class CreateJiraIssueTask(Task):
    """
    Task for creating a jira issue. For this task to function properly,
    you need a Jira account and API token.  The API token can be created at: https://id.atlassian.com/manage/api-tokens 
    The Jira account username ('JIRAUSER'), API token ('JIRATOKEN') should be set as part of a 'JIRASECRETS' object in Prefect Secrets. 

    An example 'JIRASECRETS' object looks like this:
    ```
    JIRASECRETS = { JIRATOKEN = "XXXXXXXXX", JIRAUSER = "xxxxx@yyy.com", JIRASERVER = "https://???.atlassian.net" }
    ```
    The server URL can be set as part of the 'JIRASECRETS' object ('JIRASERVER') or passed to the task as the "server_URL" argument.
    You should use the options dictionary to set the project name, issue type and assignee.  
    
    Args:
        - (str, optional):  The message you want to send to your phone; can also be provided at runtime.
        - **kwargs (Any, optional): additional keyword arguments to pass to the standard Task init method
    """

    def __init__(self, msg: str = None, **kwargs: Any):
        self.msg = msg
        super().__init__(**kwargs)

    @defaults_from_attrs("msg")
    def run(self, server_URL: str = None,
    options: dict = {},
    ) -> None:
        """
        Run method for this Task. Invoked by calling this Task after initialization within a Flow context,
        or by using `Task.bind`.

        Args:
            - msg (str): The message you want sent to your phone; defaults to the one provided
                at initialization

        Raises:
            - None

        Returns:
            - None
        """

    jira_credentials = cast(dict, prefect.client.Secret("JIRASECRETS").get())
    username = jira_credentials["JIRAUSER"]
    password = jira_credentials["JIRATOKEN"]

    if not server_URL:
        server_URL = jira_credentials["JIRASERVER"]
        pb = Pushbullet(pbtoken)


    jira = JIRA(basic_auth=(username, password), options={'server': serverURL})

    created = jira.create_issue(options)

    if not created:
        raise ValueError("Creating Jira Issue failed")

