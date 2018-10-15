import requests

from prefect.client import Secret


def get_color(state) -> str:
    colors = {
        "Retrying": "#FFFF00",
        "CachedState": "#ffa500",
        "Pending": "#d3d3d3",
        "Skipped": "#f0fff0",
        "Success": "#008000",
        "Failed": "#FF0000",
        "TriggerFailed": "#F08080",
        "Unknown": "#000000",
    }
    return colors.get(type(state).__name__, "#00000080")


def slack_message_formatter(tracked_obj, state):
    fields = []
    if state.message is not None:
        if isinstance(state.message, Exception):
            value = "```{}```".format(repr(state.message))
        else:
            value = state.message
        fields.append({"title": "Message", "value": state.message, "short": False})

    data = {
        "attachments": [
            {
                "fallback": "State change notification",
                "color": get_color(state),
                "author_name": "Prefect",
                "author_link": "https://www.prefect.io/",
                "title": type(state).__name__,
                "fields": fields,
                "title_link": "https://www.prefect.io/",
                "text": "{0} is now in a {1} state".format(
                    tracked_obj.name, type(state).__name__
                ),
                "footer": "Prefect notification",
            }
        ]
    }
    return data


def slack_notifier(tracked_obj, state, webhook_url: str = None):
    webhook_url = webhook_url or Secret("SLACK_WEBHOOK_URL").get()
    form_data = slack_message_formatter(tracked_obj, state)
    r = requests.post(webhook_url, json=form_data)
    if not r.ok:
        raise ValueError("Slack notification for {} failed".format(tracked_obj))
