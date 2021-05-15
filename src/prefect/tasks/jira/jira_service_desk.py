from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs
from typing import cast
from typing import Any


class JiraServiceDeskTask(Task):
    """
    Task for creating a Jira Service Desk customer request. For this task to function properly,
    you need a Jira account and API token.  The API token can be created at:
    https://id.atlassian.com/manage/api-tokens The Jira account username ('JIRAUSER'), API
    token ('JIRATOKEN') can be set as part of a 'JIRASECRETS' object in Prefect Secrets.

    An example 'JIRASECRETS' secret configuration looks like:

    ```toml
    [secrets]
    JIRASECRETS.JIRATOKEN = "XXXXXXXXX"
    JIRASECRETS.JIRAUSER = "xxxxx@yyy.com"
    JIRASECRETS.JIRASERVER = "https://???.atlassian.net"
    ```

    The server URL can be set as part of the 'JIRASECRETS' object ('JIRASERVER') or passed to
    the task as the "server_URL" argument.

    The service desk id and issue type will show in the URL when you raise a customer request
    in the UI.  For example, in the below URL the service desk id is "3" and the issue_type is
    10010:

    ```
    https://test.atlassian.net/servicedesk/customer/portal/3/group/3/create/10010
    ````

    Args:
        - server_url (str): the URL of your atlassian account e.g.
            "https://test.atlassian.net".  Can also be set as a Prefect Secret.
        - service_desk_id (str):  the id for your jira service desk. Can also be set at run time.
        - issue_type (int, optional): the type of issue you want to create.  Can also be set at
            run time.
        - summary (str, optional): summary or title for your issue. Can also be set at run time.
        - description (str, optional): description or additional information for the issue. Can
            also be set at run time.
        - **kwargs (Any, optional): additional keyword arguments to pass to the standard Task
            init method.
    """

    def __init__(
        self,
        server_url: str = None,
        service_desk_id: str = None,
        issue_type: int = None,
        summary: str = None,
        description: str = None,
        **kwargs: Any
    ):
        self.server_url = server_url
        self.service_desk_id = service_desk_id
        self.issue_type = issue_type
        self.summary = summary
        self.description = description
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "server_url", "service_desk_id", "issue_type", "summary", "description"
    )
    def run(
        self,
        username: str = None,
        access_token: str = None,
        server_url: str = None,
        service_desk_id: str = None,
        issue_type: int = None,
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
            - service_desk_id(str):  the key for your jira project; defaults to the one
                provided at initialization
            - issue_type (str, optional): the type of issue you want to create;
            - summary (str, optional): summary or title for your issue; defaults to the one
                provided at initialization
            - description (str, optional): description or additional information for the issue;
                defaults to the one provided at initialization

        Raises:
            - ValueError: if a `service_desk_id`, `request_type`, or `summary` are not provided

        Returns:
            - None
        """
        try:
            from jira import JIRA
        except ImportError as exc:
            raise ImportError(
                'Using Jira tasks requires Prefect to be installed with the "jira" extra.'
            ) from exc

        jira_credentials = cast(dict, Secret("JIRASECRETS").get())

        if username is None:
            username = jira_credentials["JIRAUSER"]

        if access_token is None:
            access_token = jira_credentials["JIRATOKEN"]

        if server_url is None:
            server_url = jira_credentials["JIRASERVER"]

        if issue_type is None:
            raise ValueError("An issue_type must be provided")

        if service_desk_id is None:
            raise ValueError("A service desk id must be provided")

        if summary is None:
            raise ValueError("A summary must be provided")

        jira = JIRA(basic_auth=(username, access_token), options={"server": server_url})

        options = {
            "serviceDeskId": service_desk_id,
            "requestTypeId": issue_type,
            "requestFieldValues": {"summary": summary, "description": description},
        }
        created = jira.create_customer_request(options)

        if not created:
            raise ValueError("Creating Jira Issue failed")
