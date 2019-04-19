from unittest.mock import MagicMock

import pytest

from prefect import context
from prefect.tasks.notifications import SlackTask
from prefect.utilities.configuration import set_temporary_config


class TestInitialization:
    def test_inits_with_no_args(self):
        t = SlackTask()
        assert t

    def test_kwargs_get_passed_to_task_init(self):
        t = SlackTask(name="bob", checkpoint=True, tags=["foo"])
        assert t.name == "bob"
        assert t.checkpoint is True
        assert t.tags == {"foo"}

    def test_webhook_url_pulled_from_secrets(self, monkeypatch):
        req = MagicMock()
        monkeypatch.setattr("prefect.tasks.notifications.slack_task.requests", req)
        t = SlackTask()
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with context({"secrets": dict(SLACK_WEBHOOK_URL="http://foo/bar")}):
                res = t.run(message="o hai mark")
        assert req.post.call_args[0] == ("http://foo/bar",)
        assert req.post.call_args[1]["json"]["text"] == "o hai mark"
