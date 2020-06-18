from unittest.mock import MagicMock

import pytest

from prefect import context
from prefect.tasks.notifications import EmailTask
from prefect.utilities.configuration import set_temporary_config


class TestInitialization:
    def test_inits_with_no_args(self):
        t = EmailTask()
        assert t

    def test_kwargs_get_passed_to_task_init(self):
        t = EmailTask(name="bob", checkpoint=True, tags=["foo"])
        assert t.name == "bob"
        assert t.checkpoint is True
        assert t.tags == {"foo"}

    def test_username_password_pulled_from_secrets(self, monkeypatch):
        smtp = MagicMock()
        monkeypatch.setattr("prefect.tasks.notifications.email_task.smtplib", smtp)
        t = EmailTask(msg="")
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with context({"secrets": dict(EMAIL_USERNAME="foo", EMAIL_PASSWORD="bar")}):
                res = t.run()
        assert smtp.SMTP_SSL.return_value.login.call_args[0] == ("foo", "bar")

    def test_run_raises_error_when_called_with_unsupported_smtp_type(self):
        t = EmailTask(msg="", smtp_type="TEST")
        with pytest.raises(
            ValueError, match="TEST is an unsupported value for smtp_type."
        ):
            with context({"secrets": dict(EMAIL_USERNAME="foo", EMAIL_PASSWORD="bar")}):
                res = t.run()

    def test_kwarg_for_email_from_get_passed_to_task_init(self, monkeypatch):
        smtp = MagicMock()
        monkeypatch.setattr("prefect.tasks.notifications.email_task.smtplib", smtp)
        t = EmailTask(msg="", email_from="test@lvh.me")
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with context({"secrets": dict(EMAIL_USERNAME="foo", EMAIL_PASSWORD="bar")}):
                res = t.run()
        assert smtp.SMTP_SSL.return_value.sendmail.call_args[0][0] == ("test@lvh.me")

    def test_kwargs_for_smtp_server_get_passed_to_task_init(self):
        t = EmailTask(smtp_server="mail.lvh.me", smtp_port=587, smtp_type="STARTTLS")
        assert t.smtp_server == "mail.lvh.me"
        assert t.smtp_port == 587
        assert t.smtp_type == "STARTTLS"
