"""
A state-handler that will create and assign a Jira ticket.
"""

from typing import TYPE_CHECKING, Union, cast, Optional
from datetime import datetime
from toolz import curry

import prefect


try:
    from jira import JIRA
except ImportError as import_error:
    raise ImportError(
        'Using `jira_notifier` requires Prefect to be installed with the "jira" extra.'
    ) from import_error

if TYPE_CHECKING:
    import prefect.engine.state
    import prefect.client
    from prefect import Flow, Task


def jira_message_formatter(
    tracked_obj: "Union[Flow, Task]", state: "prefect.engine.state.State"
) -> str:
    time = datetime.utcnow()
    msg = "Message from Prefect: {0} entered a {1} state at {2}".format(
        tracked_obj.name, type(state).__name__, time
    )
    return msg


@curry
def jira_notifier(
    tracked_obj: "Union[Flow, Task]",
    old_state: "prefect.engine.state.State",
    new_state: "prefect.engine.state.State",
    ignore_states: list = None,
    only_states: list = None,
    server_URL: str = None,
    options: Optional[dict] = None,
    assignee: str = "-1",
) -> "prefect.engine.state.State":
    """
    Jira Notifier requires a Jira account and API token.  The API token can be created at:
    https://id.atlassian.com/manage/api-tokens The Jira account username ('JIRAUSER'), API
    token ('JIRATOKEN') should be set as part of a 'JIRASECRETS' object in Prefect Secrets.

    An example 'JIRASECRETS' secret configuration looks like:

    ```toml
    [secrets]
    JIRASECRETS.JIRATOKEN = "XXXXXXXXX"
    JIRASECRETS.JIRAUSER = "xxxxx@yyy.com"
    JIRASECRETS.JIRASERVER = "https://???.atlassian.net"
    ```

    The server URL can be set as part of the 'JIRASECRETS' object ('JIRASERVER') or passed to
    the jira notifier state handler as the "server_URL" argument.  Jira Notifier works as a
    standalone state handler, or can be called from within a custom state handler.  This
    function is curried meaning that it can be called multiple times to partially bind any
    keyword arguments (see example below).  Jira Notifier creates a new ticket with the
    information about the task or flow it is bound to when that task or flow is in a specific
    state.  (For example it will create a ticket to tell you that the flow you set it on is in
    a failed state.) You should use the options dictionary to set the project name and issue
    type.  You can use the "assignee" argument to assign that ticket to a specific member of
    your team.

    Args:
        - tracked_obj (Task or Flow): Task or Flow object the handler is registered with
        - old_state (State): previous state of tracked object
        - new_state (State): new state of tracked object
        - options (Dictionary): Must inlucde a 'project' key and an 'issuetype' key (e.g.
            options = {'project': 'TEST', 'issuetype': {'name': 'task'}}). For jira service
            desk tickets, the issue type should use the request type id e.g. 'issuetype':
            {'id': '10010'}. A description can be added using the key 'description'. Custom
            fields can also be added e.g.  'customfield_10017': 'SDTS/flowdown'
        - ignore_states ([State], optional): list of `State` classes to ignore, e.g.,
            `[Running, Scheduled]`. If `new_state` is an instance of one of the passed states,
            no notification will occur.
        - only_states ([State], optional): similar to `ignore_states`, but instead _only_
            notifies you if the Task / Flow is in a state from the provided list of `State`
            classes
        - server_URL (String): The URL of your atlassian account e.g.
            "https://test.atlassian.net".  Can also be set as a Prefect Secret.
        - assignee: the atlassian username of the person you want to assign the ticket to.
            Defaults to "automatic" if this is not set.

    Returns:
        - State: the `new_state` object that was provided

    Raises:
        - ValueError: if the jira ticket creation or assignment fails for any reason

    Example:
        ```python
        from prefect import task
        from prefect.utilities.jira_notification import jira_notifier

        @task(state_handlers=[
            jira_notifier(
                only_states=[Failed],
                options={'project': 'TEST', 'issuetype': {'name': 'Task'}},
                assignee='tester'
            )
        ])
        def add(x, y):
            return x + y
        ```
    """

    options = options or dict()
    jira_credentials = cast(dict, prefect.client.Secret("JIRASECRETS").get())
    username = jira_credentials["JIRAUSER"]
    password = jira_credentials["JIRATOKEN"]

    if not server_URL:
        server_URL = jira_credentials["JIRASERVER"]

    ignore_states = ignore_states or []
    only_states = only_states or []

    if any([isinstance(new_state, ignored) for ignored in ignore_states]):
        return new_state

    if only_states and not any(
        [isinstance(new_state, included) for included in only_states]
    ):
        return new_state

    summary_text = str(jira_message_formatter(tracked_obj, new_state))

    options["summary"] = summary_text

    jira = JIRA(basic_auth=(username, password), options={"server": server_URL})

    created = jira.create_issue(options)
    if not created:
        raise ValueError("Creating Jira Issue for {} failed".format(tracked_obj))

    if assignee:
        assigned = jira.assign_issue(created, assignee)
        if not assigned:
            raise ValueError("Assigning Jira issue for {} failed".format(tracked_obj))

    return new_state
