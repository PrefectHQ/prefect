from unittest.mock import MagicMock

import pytest

from prefect import context
from prefect.tasks.notifications import GmailTask
from prefect.utilities.configuration import set_temporary_config


class TestInitialization:
    def test_inits_with_no_args(self):
        t = GmailTask()
        assert t

    def test_kwargs_get_passed_to_task_init(self):
        t = GmailTask(name="bob", checkpoint=True, tags=["foo"])
        assert t.name == "bob"
        assert t.checkpoint is True
        assert t.tags == {"foo"}

    def test_username_password_pulled_from_secrets(self, monkeypatch):
        smtp = MagicMock()
        monkeypatch.setattr("prefect.tasks.notifications.gmail_task.smtplib", smtp)
        t = GmailTask(msg="")
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with context({"secrets": dict(EMAIL_USERNAME="foo", EMAIL_PASSWORD="bar")}):
                res = t.run()
        assert smtp.SMTP_SSL.return_value.login.call_args[0] == ("foo", "bar")
