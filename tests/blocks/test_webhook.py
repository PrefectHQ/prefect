import pytest

from prefect.blocks.webhook import Webhook
from prefect.testing.utilities import AsyncMock


class TestWebhook:
    def test_webhook_raises_error_on_bad_request_method(self):
        for method in ["GET", "PUT", "POST", "PATCH", "DELETE"]:
            Webhook(method=method, url="http://google.com")

        for bad_method in ["get", "BLAH", ""]:
            with pytest.raises(ValueError):
                Webhook(method=bad_method, url="http://google.com")

    async def test_webhook_sends(self, monkeypatch):
        send_mock = AsyncMock()
        monkeypatch.setattr("httpx.AsyncClient.request", send_mock)

        await Webhook(
            method="POST", url="http://yahoo.com", headers={"authorization": "password"}
        ).call(payload={"event_id": "123"})

        send_mock.assert_called_with(
            method="POST",
            url="http://yahoo.com",
            headers={"authorization": "password"},
            json={"event_id": "123"},
        )

    async def test_webhook_sends_get_request_with_no_payload(self, monkeypatch):
        send_mock = AsyncMock()
        monkeypatch.setattr("httpx.AsyncClient.request", send_mock)
        await Webhook(
            method="GET", url="http://google.com", headers={"foo": "bar"}
        ).call(payload=None)

        send_mock.assert_called_with(
            method="GET", url="http://google.com", headers={"foo": "bar"}, json=None
        )

    async def test_save_and_load_webhook(self):
        await Webhook(
            method="GET", url="http://google.com", headers={"foo": "bar"}
        ).save(name="webhook-test")

        webhook = await Webhook.load(name="webhook-test")
        assert webhook.url.get_secret_value() == "http://google.com"
        assert webhook.method == "GET"
        assert webhook.headers.get_secret_value() == {"foo": "bar"}
