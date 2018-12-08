import json
import pytest
import sys
from unittest.mock import MagicMock

import prefect
from prefect import task, Task
from prefect.engine.state import (
    State,
    Running,
    Pending,
    Finished,
    Failed,
    TriggerFailed,
    CachedState,
    Scheduled,
    Retrying,
    Success,
    Skipped,
)
from prefect.utilities.notifications import (
    gmail_notifier,
    slack_message_formatter,
    slack_notifier,
)


@pytest.mark.parametrize(
    "state",
    [
        Running,
        Pending,
        Finished,
        Failed,
        TriggerFailed,
        CachedState,
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
        CachedState,
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
        CachedState,
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
        CachedState,
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
    monkeypatch.setattr(prefect.utilities.notifications.requests, "post", ok)
    new_state = Failed(message="1", result=0)
    assert slack_notifier(Task(), "", new_state) is new_state


def test_slack_notifier_ignores_ignore_states(monkeypatch):
    all_states = [
        Running,
        Pending,
        Finished,
        Failed,
        TriggerFailed,
        CachedState,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ]
    ok = MagicMock(ok=True)
    monkeypatch.setattr(prefect.utilities.notifications.requests, "post", ok)
    for state in all_states:
        s = state()
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
        CachedState,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ],
)
def test_slack_notifier_is_curried_and_ignores_ignore_states(monkeypatch, state):
    state = state()
    ok = MagicMock(ok=True)
    monkeypatch.setattr(prefect.utilities.notifications.requests, "post", ok)
    handler = slack_notifier(ignore_states=[Finished])
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
        CachedState,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ],
)
def test_slack_notifier_is_curried_and_uses_only_states(monkeypatch, state):
    state = state()
    ok = MagicMock(ok=True)
    monkeypatch.setattr(prefect.utilities.notifications.requests, "post", ok)
    handler = slack_notifier(only_states=[TriggerFailed])
    returned = handler(Task(), "", state)
    assert returned is state
    assert ok.called is isinstance(state, TriggerFailed)


def test_gmail_notifier_sends_simple_email(monkeypatch):
    smtp = MagicMock()
    sendmail = MagicMock()
    smtp.SMTP_SSL.return_value.sendmail = sendmail
    monkeypatch.setattr(prefect.utilities.notifications, "smtplib", smtp)
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
        CachedState,
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
    monkeypatch.setattr(prefect.utilities.notifications, "smtplib", smtp)
    monkeypatch.setattr(prefect.config.cloud, "use_local_secrets", True)
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
        CachedState,
        Scheduled,
        Retrying,
        Success,
        Skipped,
    ]
    smtp = MagicMock()
    sendmail = MagicMock()
    smtp.SMTP_SSL.return_value.sendmail = sendmail
    monkeypatch.setattr(prefect.config.cloud, "use_local_secrets", True)
    monkeypatch.setattr(prefect.utilities.notifications, "smtplib", smtp)
    for state in all_states:
        s = state()
        returned = gmail_notifier(Task(), "", s, ignore_states=[State])
        assert returned is s
        assert sendmail.called is False
