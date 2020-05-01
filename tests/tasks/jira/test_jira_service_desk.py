from unittest.mock import MagicMock
import prefect
from prefect import context
from prefect.tasks.jira import JiraServiceDeskTask
from prefect.utilities.configuration import set_temporary_config
import pytest

pytest.importorskip("jira")


class TestInitialization:
    def test_inits_with_no_args(self):
        t = JiraServiceDeskTask()
        assert t

    def test_kwargs_get_passed_to_task_init(self):
        t = JiraServiceDeskTask(project_name="Test", summary="test", tags=["foo"])
        assert t.project_name == "Test"
        assert t.tags == {"foo"}

    def test_token_pulled_from_secrets(self, monkeypatch):
        task = JiraServiceDeskTask(project_name="TEST", summary="test")
        client = MagicMock()
        jira = MagicMock(client=client)
        monkeypatch.setattr("prefect.tasks.jira.jira_task.JIRA", jira)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    JIRASECRETS={
                        "JIRAUSER": "Bob",
                        "JIRATOKEN": "",
                        "JIRASERVER": "https://foo/bar",
                    }
                )
            ):
                task.run()
        kwargs = jira.call_args[1]
        assert kwargs == {
            "basic_auth": ("Bob", ""),
            "options": {"server": "https://foo/bar"},
        }

    def test_raises_if_secret_not_provided(self):
        task = JiraServiceDeskTask()
        with pytest.raises(ValueError, match="Secret"):
            task.run()

    def test_raises_if_service_desk_id_not_provided(self, monkeypatch):
        task = JiraServiceDeskTask()
        client = MagicMock()
        jira = MagicMock(client=client)
        monkeypatch.setattr("prefect.tasks.jira.jira_task.JIRA", jira)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    JIRASECRETS={
                        "JIRAUSER": "Bob",
                        "JIRATOKEN": "",
                        "JIRASERVER": "https://foo/bar",
                    }
                )
            ):
                with pytest.raises(ValueError, match="service"):
                    task.run()

    def test_raises_if_summary_not_provided(self, monkeypatch):
        task = JiraTask(project_name="Test")
        client = MagicMock()
        jira = MagicMock(client=client)
        monkeypatch.setattr("prefect.tasks.jira.jira_task.JIRA", jira)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    JIRASECRETS={
                        "JIRAUSER": "Bob",
                        "JIRATOKEN": "",
                        "JIRASERVER": "https://foo/bar",
                    }
                )
            ):
                with pytest.raises(ValueError, match="summary"):
                    task.run()
