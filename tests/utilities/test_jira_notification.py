import json
import os
import sys
import tempfile
from multiprocessing.pool import ThreadPool
from unittest.mock import MagicMock

import cloudpickle
import pytest

import prefect
from prefect import Task, task
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
from prefect.utilities.jira_notification import jira_notifier


def test_jira_notifier_returns_new_state_and_old_state_is_ignored(monkeypatch):
    client = MagicMock()
    jira = MagicMock(client=client)
    monkeypatch.setattr("prefect.utilities.jira_notification.JIRA", jira)
    new_state = Failed(message="1", result=0)
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(JIRAUSER="", JIRATOKEN="", JIRASERVER="", JIRAPROJECT="")):
            assert jira_notifier(Task(), "", new_state) is new_state


# def test_slack_notifier_pulls_url_from_secret(monkeypatch):
#     post = MagicMock(ok=True)
#     monkeypatch.setattr("prefect.utilities.notifications.requests.post", post)
#     state = Failed(message="1", result=0)
#     with set_temporary_config({"cloud.use_local_secrets": True}):
#         with pytest.raises(ValueError, match="SLACK_WEBHOOK_URL"):
#             slack_notifier(Task(), "", state)

#         with prefect.context(secrets=dict(SLACK_WEBHOOK_URL="https://foo/bar")):
#             slack_notifier(Task(), "", state)

#         assert post.call_args[0][0] == "https://foo/bar"

#         with prefect.context(secrets=dict(TOP_SECRET='"42"')):
#             slack_notifier(Task(), "", state, webhook_secret="TOP_SECRET")

#         assert post.call_args[0][0] == "42"


# def test_slack_notifier_ignores_ignore_states(monkeypatch):
#     all_states = [
#         Running,
#         Pending,
#         Finished,
#         Failed,
#         TriggerFailed,
#         Cached,
#         Scheduled,
#         Retrying,
#         Success,
#         Skipped,
#     ]
#     ok = MagicMock(ok=True)
#     monkeypatch.setattr(prefect.utilities.notifications.requests, "post", ok)
#     for state in all_states:
#         s = state()
#         with set_temporary_config({"cloud.use_local_secrets": True}):
#             with prefect.context(secrets=dict(SLACK_WEBHOOK_URL="")):
#                 returned = slack_notifier(Task(), "", s, ignore_states=[State])
#         assert returned is s
#         assert ok.called is False


# @pytest.mark.parametrize(
#     "state",
#     [
#         Running,
#         Pending,
#         Finished,
#         Failed,
#         TriggerFailed,
#         Cached,
#         Scheduled,
#         Retrying,
#         Success,
#         Skipped,
#     ],
# )
# def test_slack_notifier_is_curried_and_ignores_ignore_states(monkeypatch, state):
#     state = state()
#     ok = MagicMock(ok=True)
#     monkeypatch.setattr(prefect.utilities.notifications.requests, "post", ok)
#     handler = slack_notifier(ignore_states=[Finished])
#     with set_temporary_config({"cloud.use_local_secrets": True}):
#         with prefect.context(secrets=dict(SLACK_WEBHOOK_URL="")):
#             returned = handler(Task(), "", state)
#     assert returned is state
#     assert ok.called is not state.is_finished()


# @pytest.mark.parametrize(
#     "state",
#     [
#         Running,
#         Pending,
#         Finished,
#         Failed,
#         TriggerFailed,
#         Cached,
#         Scheduled,
#         Retrying,
#         Success,
#         Skipped,
#     ],
# )
# def test_slack_notifier_is_curried_and_uses_only_states(monkeypatch, state):
#     state = state()
#     ok = MagicMock(ok=True)
#     monkeypatch.setattr(prefect.utilities.notifications.requests, "post", ok)
#     handler = slack_notifier(only_states=[TriggerFailed])
#     with set_temporary_config({"cloud.use_local_secrets": True}):
#         with prefect.context(secrets=dict(SLACK_WEBHOOK_URL="")):
#             returned = handler(Task(), "", state)
#     assert returned is state
#     assert ok.called is isinstance(state, TriggerFailed)


# def test_gmail_notifier_sends_simple_email(monkeypatch):
#     smtp = MagicMock()
#     sendmail = MagicMock()
#     smtp.SMTP_SSL.return_value.sendmail = sendmail
#     monkeypatch.setattr(prefect.utilities.notifications, "smtplib", smtp)
#     s = Failed("optional message...")

#     monkeypatch.setattr(prefect.config.cloud, "use_local_secrets", True)
#     with prefect.context(secrets=dict(EMAIL_USERNAME="alice", EMAIL_PASSWORD=1234)):
#         returned = gmail_notifier(Task(name="dud"), "", s)

#     assert returned is s
#     email_from, to, body = sendmail.call_args[0]
#     assert email_from == "notifications@prefect.io"
#     assert to == "alice"
#     assert "Failed" in body
#     assert "optional message" in body
#     assert s.color in body


# @pytest.mark.parametrize(
#     "state",
#     [
#         Running,
#         Pending,
#         Finished,
#         Failed,
#         TriggerFailed,
#         Cached,
#         Scheduled,
#         Retrying,
#         Success,
#         Skipped,
#     ],
# )
# def test_gmail_notifier_is_curried_and_uses_only_states(monkeypatch, state):
#     state = state()
#     smtp = MagicMock()
#     sendmail = MagicMock()
#     smtp.SMTP_SSL.return_value.sendmail = sendmail
#     monkeypatch.setattr(prefect.utilities.notifications, "smtplib", smtp)
#     with set_temporary_config({"cloud.use_local_secrets": True}):
#         with prefect.context(secrets=dict(EMAIL_USERNAME="", EMAIL_PASSWORD="")):
#             handler = gmail_notifier(only_states=[TriggerFailed])
#             returned = handler(Task(), "", state)
#     assert returned is state
#     assert sendmail.called is isinstance(state, TriggerFailed)


# def test_gmail_notifier_ignores_ignore_states(monkeypatch):
#     all_states = [
#         Running,
#         Pending,
#         Finished,
#         Failed,
#         TriggerFailed,
#         Cached,
#         Scheduled,
#         Retrying,
#         Success,
#         Skipped,
#     ]
#     smtp = MagicMock()
#     sendmail = MagicMock()
#     smtp.SMTP_SSL.return_value.sendmail = sendmail
#     monkeypatch.setattr(prefect.utilities.notifications, "smtplib", smtp)
#     for state in all_states:
#         s = state()
#         with set_temporary_config({"cloud.use_local_secrets": True}):
#             with prefect.context(secrets=dict(EMAIL_USERNAME="", EMAIL_PASSWORD="")):
#                 returned = gmail_notifier(Task(), "", s, ignore_states=[State])
#         assert returned is s
#         assert sendmail.called is False
