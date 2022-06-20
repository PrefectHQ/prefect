import json
import os
import sys
import tempfile
from multiprocessing.pool import ThreadPool
from unittest.mock import MagicMock

import requests
import cloudpickle
import pytest

import prefect
from prefect import Task
from prefect.engine.state import (
    Cached,
    Failed,
    Finished,
    Pending,
    Retrying,
    Running,
    Scheduled,
    Skipped,
    State,
    Success,
    TriggerFailed,
)
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.notifications import (
    callback_factory,
    gmail_notifier,
    slack_message_formatter,
    slack_notifier,
    snowflake_logger,
)


def test_callback_factory_generates_pickleable_objs():
    """
    This test does some heavy lifting to create two lambda functions,
    and then passes them through callback_factory to generate a state-handler.
    We then pickle the state handler to a temporary file, delete the functions,
    and try to unpickle the file in a new Process, asserting that the result is what we
    think it should be.
    """

    def load_bytes(fname):
        import cloudpickle

        with open(fname, "rb") as f:
            obj = cloudpickle.load(f)
        return obj(1, 2, 3)

    fn = lambda obj, state: None
    check = lambda state: True
    handler = callback_factory(fn, check)

    sd, tmp_file = tempfile.mkstemp()
    os.close(sd)
    try:
        with open(tmp_file, "wb") as bit_file:
            cloudpickle.dump(handler, bit_file)
        del fn
        del check
        pool = ThreadPool(processes=1)
        result = pool.apply_async(load_bytes, (tmp_file,))
        value = result.get()
        assert value == 3
    except Exception as exc:
        raise exc
    finally:
        os.unlink(tmp_file)


@pytest.mark.parametrize(
    "state",
    [
        Running,
        Pending,
        Finished,
        Failed,
        TriggerFailed,
        Cached,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ],
)
def test_formatter_formats_states(state):
    orig = slack_message_formatter(Task(), state())
    assert json.loads(json.dumps(orig)) == orig


@pytest.mark.parametrize(
    "state",
    [
        Running,
        Pending,
        Finished,
        Failed,
        TriggerFailed,
        Cached,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ],
)
def test_formatter_formats_states_with_string_message(state):
    orig = slack_message_formatter(Task(), state(message="I am informative"))
    assert orig["attachments"][0]["fields"][0]["value"] == "I am informative"
    assert json.loads(json.dumps(orig)) == orig


@pytest.mark.parametrize(
    "state",
    [
        Running,
        Pending,
        Finished,
        Failed,
        TriggerFailed,
        Cached,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ],
)
def test_formatter_formats_states_with_exception_message(state):
    orig = slack_message_formatter(Task(), state(result=ZeroDivisionError("Nope")))
    expected = "```ZeroDivisionError('Nope'"
    expected += ")```" if sys.version_info >= (3, 7) else ",)```"
    assert orig["attachments"][0]["fields"][0]["value"] == expected
    assert json.loads(json.dumps(orig)) == orig


def test_every_state_gets_a_unique_color():
    all_states = [
        Running,
        Pending,
        Finished,
        Failed,
        TriggerFailed,
        Cached,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ]
    colors = set()
    for state in all_states:
        color = slack_message_formatter(Task(), state())["attachments"][0]["color"]
        colors.add(color)
    assert len(colors) == len(all_states)


def test_slack_notifier_returns_new_state_and_old_state_is_ignored(monkeypatch):
    ok = MagicMock(ok=True)
    monkeypatch.setattr(requests, "post", ok)
    new_state = Failed(message="1", result=0)
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(SLACK_WEBHOOK_URL="")):
            assert slack_notifier(Task(), "", new_state) is new_state


def test_slack_notifier_pulls_url_from_secret(monkeypatch):
    post = MagicMock(ok=True)
    monkeypatch.setattr("requests.post", post)
    state = Failed(message="1", result=0)
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with pytest.raises(ValueError, match="SLACK_WEBHOOK_URL"):
            slack_notifier(Task(), "", state)

        with prefect.context(secrets=dict(SLACK_WEBHOOK_URL="https://foo/bar")):
            slack_notifier(Task(), "", state)

        assert post.call_args[0][0] == "https://foo/bar"

        with prefect.context(secrets=dict(TOP_SECRET='"42"')):
            slack_notifier(Task(), "", state, webhook_secret="TOP_SECRET")

        assert post.call_args[0][0] == "42"


def test_slack_notifier_ignores_ignore_states(monkeypatch):
    all_states = [
        Running,
        Pending,
        Finished,
        Failed,
        TriggerFailed,
        Cached,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ]
    ok = MagicMock(ok=True)
    monkeypatch.setattr(requests, "post", ok)
    for state in all_states:
        s = state()
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(SLACK_WEBHOOK_URL="")):
                returned = slack_notifier(Task(), "", s, ignore_states=[State])
        assert returned is s
        assert ok.called is False


@pytest.mark.parametrize(
    "state",
    [
        Running,
        Pending,
        Finished,
        Failed,
        TriggerFailed,
        Cached,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ],
)
def test_slack_notifier_is_curried_and_ignores_ignore_states(monkeypatch, state):
    state = state()
    ok = MagicMock(ok=True)
    monkeypatch.setattr(requests, "post", ok)
    handler = slack_notifier(ignore_states=[Finished])
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(SLACK_WEBHOOK_URL="")):
            returned = handler(Task(), "", state)
    assert returned is state
    assert ok.called is not state.is_finished()


@pytest.mark.parametrize(
    "state",
    [
        Running,
        Pending,
        Finished,
        Failed,
        TriggerFailed,
        Cached,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ],
)
def test_slack_notifier_is_curried_and_uses_only_states(monkeypatch, state):
    state = state()
    ok = MagicMock(ok=True)
    monkeypatch.setattr(requests, "post", ok)
    handler = slack_notifier(only_states=[TriggerFailed])
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(SLACK_WEBHOOK_URL="")):
            returned = handler(Task(), "", state)
    assert returned is state
    assert ok.called is isinstance(state, TriggerFailed)


def test_slack_notifier_uses_proxies(monkeypatch):
    post = MagicMock(ok=True)
    monkeypatch.setattr(requests, "post", post)
    state = Failed(message="1", result=0)
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(SLACK_WEBHOOK_URL="")):
            slack_notifier(Task(), "", state, proxies={"http": "some.proxy.I.P"})
    assert post.call_args[1]["proxies"] == {"http": "some.proxy.I.P"}


def test_gmail_notifier_sends_simple_email(monkeypatch):
    smtp = MagicMock()
    sendmail = MagicMock()
    smtp.SMTP_SSL.return_value.sendmail = sendmail
    monkeypatch.setattr(prefect.utilities.notifications.notifications, "smtplib", smtp)
    s = Failed("optional message...")

    monkeypatch.setattr(prefect.config.cloud, "use_local_secrets", True)
    with prefect.context(secrets=dict(EMAIL_USERNAME="alice", EMAIL_PASSWORD=1234)):
        returned = gmail_notifier(Task(name="dud"), "", s)

    assert returned is s
    email_from, to, body = sendmail.call_args[0]
    assert email_from == "notifications@prefect.io"
    assert to == "alice"
    assert "Failed" in body
    assert "optional message" in body
    assert s.color in body


@pytest.mark.parametrize(
    "state",
    [
        Running,
        Pending,
        Finished,
        Failed,
        TriggerFailed,
        Cached,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ],
)
def test_gmail_notifier_is_curried_and_uses_only_states(monkeypatch, state):
    state = state()
    smtp = MagicMock()
    sendmail = MagicMock()
    smtp.SMTP_SSL.return_value.sendmail = sendmail
    monkeypatch.setattr(prefect.utilities.notifications.notifications, "smtplib", smtp)
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(EMAIL_USERNAME="", EMAIL_PASSWORD="")):
            handler = gmail_notifier(only_states=[TriggerFailed])
            returned = handler(Task(), "", state)
    assert returned is state
    assert sendmail.called is isinstance(state, TriggerFailed)


def test_gmail_notifier_ignores_ignore_states(monkeypatch):
    all_states = [
        Running,
        Pending,
        Finished,
        Failed,
        TriggerFailed,
        Cached,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ]
    smtp = MagicMock()
    sendmail = MagicMock()
    smtp.SMTP_SSL.return_value.sendmail = sendmail
    monkeypatch.setattr(prefect.utilities.notifications.notifications, "smtplib", smtp)
    for state in all_states:
        s = state()
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(EMAIL_USERNAME="", EMAIL_PASSWORD="")):
                returned = gmail_notifier(Task(), "", s, ignore_states=[State])
        assert returned is s
        assert sendmail.called is False


def test_snowflake_logger_returns_new_state_and_old_state_is_ignored(monkeypatch):
    new_state = Failed(message="1", result=0)
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(
            secrets=dict(
                SNOWFLAKE_CREDS={"user": "", "password": "", "account": ""},
                LOG_TABLE_NAME_FULL="TEST_DB.TEST_SCHEMA_LOG.TEST_TABLE_LOG",
            )
        ):
            assert snowflake_logger(Task(), "", new_state, test_env=True) is new_state


def test_snowflake_logger_pulls_connection_info_from_secret(monkeypatch):
    state = Failed(message="1", result=0)
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with pytest.raises(ValueError, match="SNOWFLAKE_CREDS"):
            snowflake_logger(Task(), "", state, test_env=True)

        with prefect.context(
            secrets=dict(
                SNOWFLAKE_CREDS={"user": "test", "password": "test", "account": "test"},
                LOG_TABLE_NAME_FULL="TEST_DB.TEST_SCHEMA_LOG.TEST_TABLE_LOG",
            )
        ):
            snowflake_logger(Task(), "", state, test_env=True)


def test_snowflake_logger_ignores_ignore_states(monkeypatch):
    all_states = [
        Running,
        Pending,
        Finished,
        Failed,
        TriggerFailed,
        Cached,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ]
    for state in all_states:
        s = state()
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    SNOWFLAKE_CREDS={
                        "user": "test",
                        "password": "test",
                        "account": "test",
                    },
                    LOG_TABLE_NAME_FULL="TEST_DB.TEST_SCHEMA_LOG.TEST_TABLE_LOG",
                )
            ):
                returned = snowflake_logger(
                    Task(), "", s, ignore_states=[State], test_env=True
                )
        assert returned is s


@pytest.mark.parametrize(
    "state",
    [
        Running,
        Pending,
        Finished,
        Failed,
        TriggerFailed,
        Cached,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ],
)
def test_snowflake_logger_is_curried_and_ignores_ignore_states(monkeypatch, state):
    state = state()
    handler = snowflake_logger(ignore_states=[Finished], test_env=True)
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(
            secrets=dict(
                SNOWFLAKE_CREDS={"user": "test", "password": "test", "account": "test"},
                LOG_TABLE_NAME_FULL="TEST_DB.TEST_SCHEMA_LOG.TEST_TABLE_LOG",
            )
        ):
            returned = handler(Task(), "", state)
    assert returned is state


@pytest.mark.parametrize(
    "state",
    [
        Running,
        Pending,
        Finished,
        Failed,
        TriggerFailed,
        Cached,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ],
)
def test_snowflake_logger_is_curried_and_uses_only_states(monkeypatch, state):
    state = state()
    handler = snowflake_logger(only_states=[TriggerFailed], test_env=True)
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(
            secrets=dict(
                SNOWFLAKE_CREDS={"user": "test", "password": "test", "account": "test"},
                LOG_TABLE_NAME_FULL="TEST_DB.TEST_SCHEMA_LOG.TEST_TABLE_LOG",
            )
        ):
            returned = handler(Task(), "", state)
    assert returned is state
