"""
Tools and utilities for notifications and callbacks.
"""
import requests
from toolz import curry

from prefect.client import Secret


def get_color(state) -> str:
    colors = {
        "Retrying": "#FFFF00",
        "CachedState": "#ffa500",
        "Pending": "#d3d3d3",
        "Scheduled": "#b0c4de",
        "Skipped": "#f0fff0",
        "Success": "#008000",
        "Finished": "#ba55d3",
        "Failed": "#FF0000",
        "TriggerFailed": "#F08080",
        "Unknown": "#000000",
    }
    return colors.get(type(state).__name__, "#000000")


def slack_message_formatter(tracked_obj, state):
    # see https://api.slack.com/docs/message-attachments
    fields = []
    if state.message is not None:
        if isinstance(state.message, Exception):
            value = "```{}```".format(repr(state.message))
        else:
            value = state.message
        fields.append({"title": "Message", "value": value, "short": False})

    data = {
        "attachments": [
            {
                "fallback": "State change notification",
                "color": get_color(state),
                "author_name": "Prefect",
                "author_link": "https://www.prefect.io/",
                "author_icon": "https://emoji.slack-edge.com/TAN3D79AL/prefect/2497370f58500a5a.png",
                "title": type(state).__name__,
                "fields": fields,
                #                "title_link": "https://www.prefect.io/",
                "text": "{0} is now in a {1} state".format(
                    tracked_obj.name, type(state).__name__
                ),
                "footer": "Prefect notification",
            }
        ]
    }
    return data


@curry
def slack_notifier(
    tracked_obj,
    old_state,
    new_state,
    ignore_states: list = None,
    only_states: list = None,
    webhook_url: str = None,
):
    """
    Slack state change handler; requires having the Prefect slack app installed.
    Works as a standalone state handler, or can be called from within a custom
    state handler.  This function is curried meaning that it can be called multiple times to partially bind any keyword arguments (see example below).

    Args:
        - tracked_obj (Task or Flow): Task or Flow object the handler is
            registered with
        - old_state (State): previous state of tracked object
        - new_state (State): new state of tracked object
        - ignore_states ([State], optional): list of `State` classes to ignore,
            e.g., `[Running, Scheduled]`. If `new_state` is an instance of one of the passed states, no notification will occur.
        - only_states ([State], optional): similar to `ignore_states`, but
            instead _only_ notifies you if the Task / Flow is in a state from the provided list of `State` classes
        - webhook_url (str, optional): the Prefet slack app webhook URL; if not
            provided, will attempt to use your `"SLACK_WEBHOOK_URL"` Prefect Secret

    Returns:
        - State: the `new_state` object which was provided

    Raises:
        - ValueError: if the slack notification fails for any reason

    Example:
        ```python
        from prefect import task
        from prefect.utilities.notifications import slack_notifier

        @task(state_handlers=[slack_notifier(ignore_states=[Running])]) # uses currying
        def add(x, y):
            return x + y
        ```
    """
    webhook_url = webhook_url or Secret("SLACK_WEBHOOK_URL").get()
    ignore_states = ignore_states or []
    only_states = only_states or []

    if any([isinstance(new_state, ignored) for ignored in ignore_states]):
        return new_state

    if only_states and not any(
        [isinstance(new_state, included) for included in only_states]
    ):
        return new_state

    form_data = slack_message_formatter(tracked_obj, new_state)
    r = requests.post(webhook_url, json=form_data)
    if not r.ok:
        raise ValueError("Slack notification for {} failed".format(tracked_obj))
    return new_state
