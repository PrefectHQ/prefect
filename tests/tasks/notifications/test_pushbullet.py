from unittest.mock import MagicMock
import prefect
from prefect import context
from prefect.tasks.notifications import PushbulletTask
from prefect.utilities.configuration import set_temporary_config


class TestInitialization:
    def test_inits_with_no_args(self):
        t = PushbulletTask()
        assert t

    def test_kwargs_get_passed_to_task_init(self):
        t = PushbulletTask(msg="Test", tags=["foo"])
        assert t.msg == "Test"
        assert t.tags == {"foo"}

    def test_token_pulled_from_secrets(self, monkeypatch):
        task = PushbulletTask(msg="test")
        client = MagicMock()
        pushbullet = MagicMock(client=client)
        monkeypatch.setattr(
            "prefect.tasks.notifications.pushbullet_task.Pushbullet", pushbullet
        )
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(PUSHBULLET_TOKEN=42)):
                task.run()
        kwargs = pushbullet.call_args[0]
        assert kwargs == (42,)

    # def test_kwarg_for_notification_from_get_passed_to_task_init(self, monkeypatch):
    #     smtp = MagicMock()
    #     monkeypatch.setattr("prefect.tasks.notifications.pushbullet.smtplib", smtp)
    #     t = PushbulletTask(msg="Test")
    #     with set_temporary_config({"cloud.use_local_secrets": True}):
    #         with context({"secrets": dict(PUSHBULLET_TOKEN="foo")}):
    #             res = t.run()
    #     assert smtp.SMTP_SSL.return_value.sendmail.call_args[0][0] == ("test@lvh.me")

    # def test_kwargs_for_smtp_server_get_passed_to_task_init(self):
    #     t = EmailTask(smtp_server="mail.lvh.me", smtp_port=587, smtp_type="STARTTLS")
    #     assert t.smtp_server == "mail.lvh.me"
    #     assert t.smtp_port == 587
    #     assert t.smtp_type == "STARTTLS"
