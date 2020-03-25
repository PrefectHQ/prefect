from unittest.mock import MagicMock

import pytest
import requests

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
        monkeypatch.setattr(requests, "post", req)
        t = SlackTask()
        with set_temporary_config({"use_local_secrets": True}):
            with context({"secrets": dict(SLACK_WEBHOOK_URL="http://foo/bar")}):
                res = t.run(message="o hai mark")
        assert req.call_args[0] == ("http://foo/bar",)
        assert req.call_args[1]["json"]["text"] == "o hai mark"

    def test_custom_webhook_url_pulled_from_secrets(self, monkeypatch):
        req = MagicMock()
        monkeypatch.setattr(requests, "post", req)
        t = SlackTask(webhook_secret="MY_URL")
        with set_temporary_config({"use_local_secrets": True}):
            with context({"secrets": dict(MY_URL="http://foo/bar")}):
                res = t.run(message="o hai mark")
        assert req.call_args[0] == ("http://foo/bar",)
        assert req.call_args[1]["json"]["text"] == "o hai mark"
