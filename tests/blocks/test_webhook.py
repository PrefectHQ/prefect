import pytest

from prefect.blocks.webhook import Webhook
from prefect.testing.utilities import AsyncMock

RESTRICTED_URLS = [
    ("", ""),
    (" ", ""),
    ("[]", ""),
    ("not a url", ""),
    ("http://", ""),
    ("https://", ""),
    ("http://[]/foo/bar", ""),
    ("ftp://example.com", "HTTP and HTTPS"),
    ("gopher://example.com", "HTTP and HTTPS"),
    ("https://localhost", "private address"),
    ("https://127.0.0.1", "private address"),
    ("https://[::1]", "private address"),
    ("https://[fc00:1234:5678:9abc::10]", "private address"),
    ("https://[fd12:3456:789a:1::1]", "private address"),
    ("https://[fe80::1234:5678:9abc]", "private address"),
    ("https://10.0.0.1", "private address"),
    ("https://10.255.255.255", "private address"),
    ("https://172.16.0.1", "private address"),
    ("https://172.31.255.255", "private address"),
    ("https://192.168.1.1", "private address"),
    ("https://192.168.1.255", "private address"),
    ("https://169.254.0.1", "private address"),
    ("https://169.254.169.254", "private address"),
    ("https://169.254.254.255", "private address"),
    # These will resolve to a private address in production, but not in tests,
    # so we'll use "resolve" as the reason to catch both cases
    ("https://metadata.google.internal", "resolve"),
    ("https://anything.privatecloud", "resolve"),
    ("https://anything.privatecloud.svc", "resolve"),
    ("https://anything.privatecloud.svc.cluster.local", "resolve"),
    ("https://cluster-internal", "resolve"),
    ("https://network-internal.cloud.svc", "resolve"),
    ("https://private-internal.cloud.svc.cluster.local", "resolve"),
]


class TestWebhook:
    def test_webhook_raises_error_on_bad_request_method(self):
        for method in ["GET", "PUT", "POST", "PATCH", "DELETE"]:
            Webhook(method=method, url="http://google.com")
            Webhook(method=method, url="http://google.com", verify=False)

        for bad_method in ["get", "BLAH", ""]:
            with pytest.raises(ValueError):
                Webhook(method=bad_method, url="http://google.com")
                Webhook(method=bad_method, url="http://google.com", verify=False)

    def test_insecure_webhook_set(self):
        insecure_webhook = Webhook(method="GET", url="http://google.com", verify=False)
        assert not getattr(insecure_webhook, "verify")
        assert (
            insecure_webhook._client._transport._pool._ssl_context.verify_mode.name
            == "CERT_NONE"
        )

        secure_webhook = Webhook(method="GET", url="http://google.com")
        assert (
            secure_webhook._client._transport._pool._ssl_context.verify_mode.name
            == "CERT_REQUIRED"
        )

    @pytest.mark.parametrize("value, reason", RESTRICTED_URLS)
    async def test_webhook_must_not_point_to_restricted_urls(
        self, value: str, reason: str
    ):
        secure_webhook = Webhook(url=value, allow_private_urls=False)

        with pytest.raises(ValueError, match=f"is not a valid URL.*{reason}"):
            await secure_webhook.call(payload="some payload")

        insecure_webhook = Webhook(url=value, allow_private_urls=False, verify=False)

        with pytest.raises(ValueError, match=f"is not a valid URL.*{reason}"):
            await insecure_webhook.call(payload="some payload")

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

        await Webhook(
            method="POST",
            url="http://yahoo.com",
            headers={"authorization": "password"},
            verify=False,
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

        await Webhook(
            method="GET", url="http://google.com", headers={"foo": "bar"}, verify=False
        ).call(payload=None)

        send_mock.assert_called_with(
            method="GET", url="http://google.com", headers={"foo": "bar"}, json=None
        )

    async def test_save_and_load_webhook(self):
        await Webhook(
            method="GET", url="http://google.com", headers={"foo": "bar"}
        ).save(name="secure-webhook-test")

        secure_webhook = await Webhook.load(name="secure-webhook-test")
        assert secure_webhook.url.get_secret_value() == "http://google.com"
        assert secure_webhook.method == "GET"
        assert secure_webhook.headers.get_secret_value() == {"foo": "bar"}

        await Webhook(
            method="GET", url="http://google.com", headers={"foo": "bar"}, verify=False
        ).save(name="insecure-webhook-test")

        insecure_webhook = await Webhook.load(name="insecure-webhook-test")
        assert insecure_webhook.url.get_secret_value() == "http://google.com"
        assert insecure_webhook.method == "GET"
        assert insecure_webhook.headers.get_secret_value() == {"foo": "bar"}
