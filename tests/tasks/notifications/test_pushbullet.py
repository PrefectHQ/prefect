from unittest.mock import MagicMock
import prefect
from prefect import context
from prefect.tasks.notifications import PushbulletTask
from prefect.utilities.configuration import set_temporary_config
import pytest

pytest.importorskip("pushbullet")


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
        monkeypatch.setattr("pushbullet.Pushbullet", pushbullet)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(PUSHBULLET_TOKEN=42)):
                task.run()
        kwargs = pushbullet.call_args[0]
        assert kwargs == (42,)

    def test_raises_if_secret_not_provided(self):
        task = PushbulletTask()
        with pytest.raises(ValueError, match="Secret"):
            task.run()

    def test_raises_if_message_not_provided(self, monkeypatch):
        task = PushbulletTask()
        client = MagicMock()
        pushbullet = MagicMock(client=client)
        monkeypatch.setattr("pushbullet.Pushbullet", pushbullet)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(PUSHBULLET_TOKEN=42)):
                with pytest.raises(ValueError, match="message"):
                    task.run()
