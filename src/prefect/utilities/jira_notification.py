"""
A state-handler that will create and assign a Jira ticket. 
"""

from typing import TYPE_CHECKING, Any, Callable, Union, cast
from datetime import datetime
from toolz import curry

import prefect

try:
    from jira import JIRA
except ImportError:
    raise ImportError(
        'Using `jira_notifier` requires Prefect to be installed with the "jira" extra.'
    )

if TYPE_CHECKING:
    import prefect.engine.state
    import prefect.client
    from prefect import Flow, Task

TrackedObjectType = Union["Flow", "Task"]


def jira_message_formatter(
    tracked_obj: TrackedObjectType, state: "prefect.engine.state.State"
) -> str:
    time = datetime.utcnow()
    msg = "Message from Prefect.io: {0} is in a {1} state at {2}".format(
        tracked_obj.name, type(state).__name__, time
    )
    return msg


@curry
def jira_notifier(
    tracked_obj: TrackedObjectType,
    old_state: "prefect.engine.state.State",
    new_state: "prefect.engine.state.State",
    ignore_states: list = None
    only_states: list = None
    server_URL: str = None
    options
) -> "prefect.engine.state.State":
    """
    Jira Notifier requires a Jira account and API token.  They API token can be created at: https://id.atlassian.com/manage/api-tokens 
    The Jira account username ('JIRAUSER'), API token ('JIRATOKEN') and server URL ('JIRASERVER') should be set as Prefect Secrets. 
    Jira Notifier works as a standalone state handler, or can be called from within a custom
    state handler.  This function is curried meaning that it can be called multiple times to partially bind any keyword arguments (see example below).
    Jira Notifier creates a new ticket with the information about the task or flow it is bound to when that task or flow is in a specific state. 
    (For example it will create a ticket to tell you that the flow you set it on is in a failed state.)  
    You can use the "assignee" argument to assign that ticket to a specific member of your team.

    Args:
        - tracked_obj (Task or Flow): Task or Flow object the handler is
            registered with
        - old_state (State): previous state of tracked object
        - new_state (State): new state of tracked object
        - ignore_states ([State], optional): list of `State` classes to ignore,
            e.g., `[Running, Scheduled]`. If `new_state` is an instance of one of the passed states, no notification will occur.
        - only_states ([State], optional): similar to `ignore_states`, but
            instead _only_ notifies you if the Task / Flow is in a state from the provided list of `State` classes
        - project_name (String): The name of the project you want to create the new ticket in.  Can also be set as a Prefect Secret. 
        - assignee - the atlassian username of the person you want to assign the ticket to.  Defaults to "automatic" if this is not set. 

    Returns:
        - State: the `new_state` object that was provided

    Raises:
        - ValueError: if the jira ticket creation or assignment fails for any reason

    Example:
        ```python
        from prefect import task
        from prefect.utilities.jira_notification import jira_notifier

        @task(state_handlers=[jira_notifier(only_states=[Failed], project_name='Test', assignee='bob')]) # uses currying
        def add(x, y):
            return x + y
        ```
    """

    jira_credentials = Secret(jira_credentials_secret).get()
    username = jira_credentials['JIRAUSER']
    password = jira_credentials['JIRATOKEN']

    if not serverURL:
    serverURL = jira_credentials['JIRASERVER']
    # username = cast(str, prefect.client.Secret("JIRAUSER").get())
    # password = cast(str, prefect.client.Secret("JIRATOKEN").get())
    # serverURL = cast(str, prefect.client.Secret("JIRASERVER").get())


    # ignore_states = options['ignore_states'] or [] 
    # only_states = options['only_states'] or [] 
    # project_name: options['project_name'] or []
    # assignee: str = "-1",

    ignore_states = ignore_states or []
    only_states = only_states or []

    if any([isinstance(new_state, ignored) for ignored in ignore_states]):
        return new_state

    if only_states and not any(
        [isinstance(new_state, included) for included in only_states]
    ):
        return new_state

    if not options['project_name']:
        options['project_name'] = jira_credentials["JIRAPROJECT"]
        # project_name = cast(str, prefect.client.Secret("JIRAPROJECT").get())
    if not options['issue_type']:
        options['issue_type'] = {"name": "Task"}

    options['summary_text'] = str(jira_message_formatter(tracked_obj, new_state))


    jira = JIRA(basic_auth=(username, password), options={"server": serverURL})
    created = jira.create_issue(
        options
    )
    if not created:
        raise ValueError("Creating Jira Issue for {} failed".format(tracked_obj))
    assigned = jira.assign_issue(created, assignee)
    if not assigned:
        raise ValueError("Assigning Jira issue for {} failed".format(tracked_obj))
    return new_state
