"""
Tools and utilities for notifications and callbacks.

For an in-depth guide to setting up your system for using Slack notifications, [please see our
tutorial](/core/advanced_tutorials/slack-notifications.html).
"""
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING, Any, Callable, Union, cast

from toolz import curry

import prefect

if TYPE_CHECKING:
    import prefect.engine.state
    import prefect.client
    from prefect import Flow, Task  # noqa

TrackedObjectType = Union["Flow", "Task"]

__all__ = ["callback_factory", "gmail_notifier", "slack_notifier", "snowflake_logger"]


def callback_factory(
    fn: Callable[[Any, "prefect.engine.state.State"], Any],
    check: Callable[["prefect.engine.state.State"], bool],
) -> Callable:
    """
    Utility for generating state handlers that serve as callbacks, under arbitrary
    state-based checks.

    Args:
        - fn (Callable): a function with signature `fn(obj, state: State) -> None`
            that will be called anytime the associated state-check passes; in general, it is
            expected that this function will have side effects (e.g., sends an email).  The
            first argument to this function is the `Task` or `Flow` it is attached to.
        - check (Callable): a function with signature `check(state: State) -> bool`
            that is used for determining when the callback function should be called

    Returns:
        - state_handler (Callable): a state handler function that can be attached to both Tasks
            and Flows

    Example:
        ```python
        from prefect import Task, Flow
        from prefect.utilities.notifications import callback_factory

        fn = lambda obj, state: print(state)
        check = lambda state: state.is_successful()
        callback = callback_factory(fn, check)

        t = Task(state_handlers=[callback])
        f = Flow("My Example Flow", tasks=[t], state_handlers=[callback])
        f.run()
        # prints:
        # Success("Task run succeeded.")
        # Success("All reference tasks succeeded.")
        ```
    """

    def state_handler(
        obj: Any,
        old_state: "prefect.engine.state.State",
        new_state: "prefect.engine.state.State",
    ) -> "prefect.engine.state.State":
        if check(new_state) is True:
            fn(obj, new_state)
        return new_state

    return state_handler


def email_message_formatter(
    tracked_obj: TrackedObjectType, state: "prefect.engine.state.State", email_to: str
) -> str:
    if isinstance(state.result, Exception):
        msg = "<pre>{}</pre>".format(repr(state.result))
    else:
        msg = '"{}"'.format(state.message)

    html = """
    <html>
      <head></head>
      <body>
        <table align="left" border="0" cellpadding="2px" cellspacing="2px">
          <tr>
            <td style="border-left: 2px solid {color};">
              <img src="https://emoji.slack-edge.com/TAN3D79AL/prefect/2497370f58500a5a.png">
            </td>
            <td style="border-left: 2px solid {color}; padding-left: 6px;">
              {text}
            </td>
          </tr>
        </table>
      </body>
    </html>
    """
    color = state.color
    text = """
    <pre>{name}</pre> is now in a <font color="{color}"><b>{state}</b></font> state
    <br><br>
    Message: {msg}
    """.format(
        name=tracked_obj.name, color=state.color, state=type(state).__name__, msg=msg
    )

    contents = MIMEMultipart("alternative")
    contents.attach(MIMEText(text, "plain"))
    contents.attach(MIMEText(html.format(color=color, text=text), "html"))

    contents["Subject"] = Header(
        "Prefect state change notification for {}".format(tracked_obj.name), "UTF-8"
    )
    contents["From"] = "notifications@prefect.io"
    contents["To"] = email_to

    return contents.as_string()


def slack_message_formatter(
    tracked_obj: TrackedObjectType,
    state: "prefect.engine.state.State",
    backend_info: bool = True,
) -> dict:
    # see https://api.slack.com/docs/message-attachments
    fields = []
    if isinstance(state.result, Exception):
        value = "```{}```".format(repr(state.result))
    else:
        value = cast(str, state.message)
    if value is not None:
        fields.append({"title": "Message", "value": value, "short": False})

    notification_payload = {
        "fallback": "State change notification",
        "color": state.color,
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

    if backend_info and prefect.context.get("flow_run_id"):
        url = None

        if isinstance(tracked_obj, prefect.Flow):
            url = prefect.client.Client().get_cloud_url(
                "flow-run", prefect.context["flow_run_id"]
            )
        elif isinstance(tracked_obj, prefect.Task):
            url = prefect.client.Client().get_cloud_url(
                "task-run", prefect.context.get("task_run_id", "")
            )

        if url:
            notification_payload.update(title_link=url)

    data = {"attachments": [notification_payload]}
    return data


@curry
def gmail_notifier(
    tracked_obj: TrackedObjectType,
    old_state: "prefect.engine.state.State",
    new_state: "prefect.engine.state.State",
    ignore_states: list = None,
    only_states: list = None,
) -> "prefect.engine.state.State":
    """
    Email state change handler - configured to work solely with Gmail; works as a standalone
    state handler, or can be called from within a custom state handler.  This function is
    curried meaning that it can be called multiple times to partially bind any keyword
    arguments (see example below).

    The username and password Gmail credentials will be taken from your `"EMAIL_USERNAME"` and
    `"EMAIL_PASSWORD"` secrets, respectively; note the username will also serve as the
    destination email address for the notification.

    Args:
        - tracked_obj (Task or Flow): Task or Flow object the handler is registered with
        - old_state (State): previous state of tracked object
        - new_state (State): new state of tracked object
        - ignore_states ([State], optional): list of `State` classes to ignore, e.g.,
            `[Running, Scheduled]`. If `new_state` is an instance of one of the passed states,
            no notification will occur.
        - only_states ([State], optional): similar to `ignore_states`, but instead _only_
            notifies you if the Task / Flow is in a state from the provided list of `State`
            classes

    Returns:
        - State: the `new_state` object that was provided

    Raises:
        - ValueError: if the email notification fails for any reason

    Example:
        ```python
        from prefect import task
        from prefect.utilities.notifications import gmail_notifier

        @task(state_handlers=[gmail_notifier(ignore_states=[Running])]) # uses currying
        def add(x, y):
            return x + y
        ```
    """
    username = cast(str, prefect.client.Secret("EMAIL_USERNAME").get())
    password = cast(str, prefect.client.Secret("EMAIL_PASSWORD").get())
    ignore_states = ignore_states or []
    only_states = only_states or []

    if any(isinstance(new_state, ignored) for ignored in ignore_states):
        return new_state

    if only_states and not any(
        [isinstance(new_state, included) for included in only_states]
    ):
        return new_state

    body = email_message_formatter(tracked_obj, new_state, username)

    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(username, password)
    try:
        server.sendmail("notifications@prefect.io", username, body)
    except Exception as exc:
        raise ValueError(
            "Email notification for {} failed".format(tracked_obj)
        ) from exc
    finally:
        server.quit()

    return new_state


@curry
def slack_notifier(
    tracked_obj: TrackedObjectType,
    old_state: "prefect.engine.state.State",
    new_state: "prefect.engine.state.State",
    ignore_states: list = None,
    only_states: list = None,
    webhook_secret: str = None,
    backend_info: bool = True,
    proxies: dict = None,
) -> "prefect.engine.state.State":
    """
    Slack state change handler; requires having the Prefect slack app installed.  Works as a
    standalone state handler, or can be called from within a custom state handler.  This
    function is curried meaning that it can be called multiple times to partially bind any
    keyword arguments (see example below).

    Args:
        - tracked_obj (Task or Flow): Task or Flow object the handler is
            registered with
        - old_state (State): previous state of tracked object
        - new_state (State): new state of tracked object
        - ignore_states ([State], optional): list of `State` classes to ignore, e.g.,
            `[Running, Scheduled]`. If `new_state` is an instance of one of the passed states,
            no notification will occur.
        - only_states ([State], optional): similar to `ignore_states`, but instead _only_
            notifies you if the Task / Flow is in a state from the provided list of `State`
            classes
        - webhook_secret (str, optional): the name of the Prefect Secret that stores your slack
            webhook URL; defaults to `"SLACK_WEBHOOK_URL"`
        - backend_info (bool, optional): Whether to supply slack notification with urls
            pointing to backend pages; defaults to True
        - proxies (dict), optional): `dict` with "http" and/or "https" keys, passed to
         `requests.post` - for situations where a proxy is required to send requests to the
          Slack webhook

    Returns:
        - State: the `new_state` object that was provided

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
    webhook_url = cast(
        str, prefect.client.Secret(webhook_secret or "SLACK_WEBHOOK_URL").get()
    )
    ignore_states = ignore_states or []
    only_states = only_states or []

    if any(isinstance(new_state, ignored) for ignored in ignore_states):
        return new_state

    if only_states and not any(
        [isinstance(new_state, included) for included in only_states]
    ):
        return new_state

    # 'import requests' is expensive time-wise, we should do this just-in-time to keep
    # the 'import prefect' time low
    import requests

    form_data = slack_message_formatter(tracked_obj, new_state, backend_info)
    r = requests.post(webhook_url, json=form_data, proxies=proxies)
    if not r.ok:
        raise ValueError("Slack notification for {} failed".format(tracked_obj))
    return new_state


def snowflake_message_formatter(
    tracked_obj: TrackedObjectType,
    state: "prefect.engine.state.State",
) -> dict:
    # see https://api.slack.com/docs/message-attachments
    fields = []
    if isinstance(state.result, Exception):
        value = "{}".format(repr(state.result))
    else:
        value = cast(str, state.message)
    if value is not None:
        fields.append({"value": value.replace("'", "''")})

    notification_payload = {
        "flow_id": prefect.context.get("flow_run_id"),
        "flow_name": prefect.context.get("flow_name"),
        "task_name": tracked_obj.name,
        "state": type(state).__name__,
        "message": fields,
    }

    return notification_payload


@curry
def snowflake_logger(
    tracked_obj: TrackedObjectType,
    old_state: "prefect.engine.state.State",
    new_state: "prefect.engine.state.State",
    ignore_states: list = None,
    only_states: list = None,
    snowflake_secret: str = None,
    snowflake_log_table_name: str = None,
    test_env: bool = False,
) -> "prefect.engine.state.State":
    """
    Snowflake state change handler/logger; requires having the Prefect Snowflake app installed.  Works as a
    standalone state handler, or can be called from within a custom state handler.  This
    function is curried meaning that it can be called multiple times to partially bind any
    keyword arguments (see example below).
    Args:
        - tracked_obj (Task or Flow): Task or Flow object the handler is
            registered with
        - old_state (State): previous state of tracked object
        - new_state (State): new state of tracked object
        - ignore_states ([State], optional): list of `State` classes to ignore, e.g.,
            `[Running, Scheduled]`. If `new_state` is an instance of one of the passed states,
            no notification will occur.
        - only_states ([State], optional): similar to `ignore_states`, but instead _only_
            notifies you if the Task / Flow is in a state from the provided list of `State`
            classes
        - snowflake_secret (str, optional): the name of the Prefect Secret that stores your Snowflake
            credentials; defaults to `"SNOWFLAKE_CREDS"`
        - snowflake_log_table_name (str, optional): the fully qualified Snowflake log table name e.g. DB.SCHEMA.TABLE
        - test_env (bool): Only used for testing and defaults to False
    Returns:
        - State: the `new_state` object that was provided
    Raises:
        - ValueError: if the snowflake logger fails for any reason
    Example:
        ```python
        from prefect import task
        from prefect.utilities.notifications import snowflake_logger
        @task(state_handlers=[snowflake_logger(ignore_states=[Running])]) # uses currying
        def add(x, y):
            return x + y
        ```
    """
    # import SnowflakeQuery here to avoid circular import error
    from prefect.tasks.snowflake import SnowflakeQuery

    ignore_states = ignore_states or []
    only_states = only_states or []

    if any(isinstance(new_state, ignored) for ignored in ignore_states):
        return new_state

    if only_states and not any(
        [isinstance(new_state, included) for included in only_states]
    ):
        return new_state

    # 'import requests' is expensive time-wise, we should do this just-in-time to keep
    # the 'import prefect' time low

    # get the secret
    sf_secret = prefect.client.Secret(snowflake_secret or "SNOWFLAKE_CREDS").get()
    sf_secret_dict = sf_secret if sf_secret is not None else {}

    # get formatted message and destruct it
    row_data = snowflake_message_formatter(tracked_obj, new_state)
    flow_id = row_data.get("flow_id")
    flow_name = row_data.get("flow_name")
    task_name = row_data.get("task_name")
    state = row_data.get("state")
    message = row_data.get("message") if row_data.get("message") != [] else ""

    # get fully qualified Snowflake log table name e.g. DB.SCHEMA.TABLE
    full_log_table_name = prefect.client.Secret(
        snowflake_log_table_name or "LOG_TABLE_NAME_FULL"
    ).get()
    full_log_table_name_list = (
        full_log_table_name.split(".") if full_log_table_name else "DB.SCHEMA.TABLE"
    )
    DB_NAME = full_log_table_name_list[0]
    SCHEMA_NAME = full_log_table_name_list[1]
    TABLE_NAME = full_log_table_name_list[2]

    sql = (
        f"INSERT INTO {DB_NAME}.{SCHEMA_NAME}.{TABLE_NAME} (FLOW_ID, FLOW_NAME, TASK_NAME, STATE, MESSAGE, "
        f"INGESTED_AT) VALUES ('{flow_id}','{flow_name}','{task_name}','{state}','{message}',CURRENT_TIMESTAMP());"
    )

    sf_user = sf_secret_dict.get("user", None)
    sf_password = sf_secret_dict.get("password", None)
    sf_account = sf_secret_dict.get("account", None)
    sf_role = sf_secret_dict.get("role", None)
    sf_warehouse = sf_secret_dict.get("warehouse", None)
    sf_private_key = sf_secret_dict.get("private_key", None)

    # adding extra check to handle testing
    # at this point it would just test the original SnowflakeQuery Task
    # and that seems unnecessary
    if test_env:
        print(sql)
    else:
        # Insert log data about Task into LOG table
        SnowflakeQuery().run(
            user=sf_user,
            password=sf_password,
            account=sf_account,
            role=sf_role,
            warehouse=sf_warehouse,
            private_key=sf_private_key,
            query=sql,
        )
    return new_state
