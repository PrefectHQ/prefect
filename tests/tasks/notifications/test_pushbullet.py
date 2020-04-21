from unittest.mock import MagicMock

import pytest
import prefect
from prefect import context
from prefect.tasks.notifications.pushbullet import PushBulletTask

from prefect.utilities.configuration import set_temporary_config

pytest.importorskip("pushbullet")

class TestInitialization:
    def test_inits_with_no_args(self):
        t = PushBulletTask()
        assert t

    def test_kwargs_get_passed_to_task_init(self):
        t = PushBulletTask(msg="Test", tags=['foo'])
        assert t.msg == "Test"
        assert t.tags == {'foo'}

    def test_token_pulled_from_secrets(self, monkeypatch):
        task = PushBulletTask(msg="test")
        client = MagicMock()
        pushbullet = MagicMock(client=client)
        # Pushbullet = MagicMock(client=client)
        monkeypatch.setattr("prefect.tasks.notifications.pushbullet.Pushbullet", pushbullet)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    
                    PUSHBULLET_TOKEN={"key":42}
                )
            ):
                task.run()
        kwargs = client.call_args[1]
        assert kwargs == {"PUSHBULLET_TOKEN": "42"}


    # def test_kwarg_for_notification_from_get_passed_to_task_init(self, monkeypatch):
    #     smtp = MagicMock()
    #     monkeypatch.setattr("prefect.tasks.notifications.pushbullet.smtplib", smtp)
    #     t = PushBulletTask(msg="Test")
    #     with set_temporary_config({"cloud.use_local_secrets": True}):
    #         with context({"secrets": dict(PUSHBULLET_TOKEN="foo")}):
    #             res = t.run()
    #     assert smtp.SMTP_SSL.return_value.sendmail.call_args[0][0] == ("test@lvh.me")

    # def test_kwargs_for_smtp_server_get_passed_to_task_init(self):
    #     t = EmailTask(smtp_server="mail.lvh.me", smtp_port=587, smtp_type="STARTTLS")
    #     assert t.smtp_server == "mail.lvh.me"
    #     assert t.smtp_port == 587
    #     assert t.smtp_type == "STARTTLS"
