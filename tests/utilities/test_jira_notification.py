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


def test_jira_notifier_pulls_creds_from_secret(monkeypatch):
    client = MagicMock()
    jira = MagicMock(client=client)
    monkeypatch.setattr("prefect.utilities.jira_notification.JIRA", jira)
    state = Failed(message="1", result=0)
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(JIRAUSER="Bob", JIRATOKEN="", JIRASERVER="https://foo/bar", JIRAPROJECT="")):
            jira_notifier(Task(), "", state)
            
        with pytest.raises(ValueError, match="JIRAUSER"):
            jira_notifier(Task(), "", state)
            

        kwargs = jira.call_args[1]
        assert kwargs == {'basic_auth': ('Bob', ''), 'options': {'server': 'https://foo/bar'}}

        

def test_jira_notifier_ignores_ignore_states(monkeypatch):
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
    client = MagicMock()
    jira = MagicMock(client=client)
    monkeypatch.setattr("prefect.utilities.jira_notification.JIRA", jira)
    for state in all_states:
        s = state()
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(JIRAUSER="Bob", JIRATOKEN="", JIRASERVER="https://foo/bar", JIRAPROJECT="")):
                returned = jira_notifier(Task(), "", s, ignore_states=[State])
        assert returned is s
        assert jira.called is False


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

def test_jira_notifier_is_curried_and_ignores_ignore_states(monkeypatch, state):
    state = state()
    client = MagicMock()
    jira = MagicMock(client=client)
    monkeypatch.setattr("prefect.utilities.jira_notification.JIRA", jira)
    handler = jira_notifier(ignore_states=[Finished])
    with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(JIRAUSER="Bob", JIRATOKEN="", JIRASERVER="https://foo/bar", JIRAPROJECT="")):
                returned = handler(Task(), "", state)
    assert returned is state
    assert jira.called is not state.is_finished()


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
def test_jira_notifier_is_curried_and_uses_only_states(monkeypatch, state):
    state = state()
    client = MagicMock()
    jira = MagicMock(client=client)
    monkeypatch.setattr("prefect.utilities.jira_notification.JIRA", jira)
    handler = jira_notifier(only_states=[TriggerFailed])
    with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(JIRAUSER="Bob", JIRATOKEN="", JIRASERVER="https://foo/bar", JIRAPROJECT="")):
                returned = handler(Task(), "", state)
    assert returned is state
    assert jira.called is isinstance(state, TriggerFailed)

