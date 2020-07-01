from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs
from typing import cast
from typing import Any

try:
    from jira import JIRA
except ImportError:
    pass


class JiraTask(Task):
    """
    Task for creating a jira issue. For this task to function properly, you need a Jira account
    and API token.  The API token can be created at: https://id.atlassian.com/manage/api-tokens
    The Jira account username ('JIRAUSER'), API token ('JIRATOKEN') can be set as part of a
    'JIRASECRETS' object in Prefect Secrets.

    An example 'JIRASECRETS' secret configuration looks like:

    ```toml
    [secrets]
    JIRASECRETS.JIRATOKEN = "XXXXXXXXX"
    JIRASECRETS.JIRAUSER = "xxxxx@yyy.com"
    JIRASECRETS.JIRASERVER = "https://???.atlassian.net"
    ```

    The server URL can be set as part of the 'JIRASECRETS' object ('JIRASERVER') or passed to
    the task as the "server_URL" argument.

    Args:
        - server_url (str): the URL of your atlassian account e.g.
            "https://test.atlassian.net".  Can also be set as a Prefect Secret.
        - project_name(str):  the key for your jira project. Can also be set at run time.
        - assignee (str, optional): the atlassian accountId of the person you want to assign
            the ticket to.  Defaults to "automatic" if this is not set. Can also be set at run
            time.
        - issue_type (str, optional): the type of issue you want to create.  Can also be set at
            run time. Defaults to 'Task'.
        - summary (str, optional): summary or title for your issue. Can also be set at run time.
        - description (str, optional): description or additional information for the issue. Can
            also be set at run time.
        - **kwargs (Any, optional): additional keyword arguments to pass to the standard Task
            init method.
    """

    def __init__(
        self,
        server_url: str = None,
        project_name: str = None,
        assignee: str = "-1",
        issue_type: str = None,
        summary: str = None,
        description: str = None,
        **kwargs: Any
    ):
        self.server_url = server_url
        self.project_name = project_name
        self.assignee = assignee
        self.issue_type = issue_type
        self.summary = summary
        self.description = description
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "server_url", "project_name", "assignee", "issue_type", "summary", "description"
    )
    def run(
        self,
        username: str = None,
        access_token: str = None,
        server_url: str = None,
        project_name: str = None,
        assignee: str = "-1",
        issue_type: str = None,
        summary: str = None,
        description: str = None,
    ) -> None:
        """
        Run method for this Task. Invoked by calling this Task after initialization within a
        Flow context, or by using `Task.bind`.

        Args:
            - username(str): the jira username, provided with a Prefect secret (defaults to
                JIRAUSER in JIRASECRETS)
            - access_token (str): a Jira access token, provided with a Prefect secret (defaults
                to JIRATOKEN in JIRASECRETS)
            - server_url (str): the URL of your atlassian account e.g.
                "https://test.atlassian.net".  Can also be set as a Prefect Secret. Defaults to
                the one provided at initialization
            - project_name(str):  the key for your jira project; defaults to the one provided
                at initialization
            - assignee (str, optional): the atlassian accountId of the person you want to
                assign the ticket to; defaults to "automatic" if this is not set; defaults to
                the one provided at initialization
            - issue_type (str, optional): the type of issue you want to create; defaults to
                'Task'
            - summary (str, optional): summary or title for your issue; defaults to the one
                provided at initialization
            - description (str, optional): description or additional information for the issue;
                defaults to the one provided at initialization

        Raises:
            - ValueError: if a `project_name` or 'summary' are not provided

        Returns:
            - None
        """

        jira_credentials = cast(dict, Secret("JIRASECRETS").get())

        if username is None:
            username = jira_credentials["JIRAUSER"]

        if access_token is None:
            access_token = jira_credentials["JIRATOKEN"]

        if server_url is None:
            server_url = jira_credentials["JIRASERVER"]

        if issue_type is None:
            issue_type = "Task"

        if project_name is None:
            raise ValueError("A project name must be provided")

        if summary is None:
            raise ValueError("A summary must be provided")

        jira = JIRA(basic_auth=(username, access_token), options={"server": server_url})

        options = {
            "project": project_name,
            "assignee": {"accountId": assignee},
            "issuetype": {"name": issue_type},
            "summary": summary,
            "description": description,
        }
        created = jira.create_issue(options)

        if not created:
            raise ValueError("Creating Jira Issue failed")
