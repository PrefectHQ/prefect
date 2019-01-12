import json
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from prefect.client import Client
from prefect.engine.cloud import CloudResultHandler
from prefect.utilities.configuration import set_temporary_config


def requests_post(*args, result=None, **kwargs):
    return dict(uri=json.dumps(result))


class TestCloudHandler:
    def test_cloud_handler_initializes_with_no_args(self):
        handler = CloudResultHandler()
        assert handler.client is None
        assert handler.result_handler_service is None

    def test_cloud_handler_pulls_settings_from_config_after_first_method_call(
        self, monkeypatch
    ):
        client = MagicMock(post=requests_post)
        monkeypatch.setattr(
            "prefect.engine.cloud.result_handler.Client", MagicMock(return_value=client)
        )
        with set_temporary_config({"cloud.result_handler": "http://foo.bar:4204"}):
            handler = CloudResultHandler()
            handler.serialize("random string")
        assert handler.result_handler_service == "http://foo.bar:4204"

    @pytest.mark.parametrize("data", [None, "my_string", 42])
    def test_cloud_handler_sends_jsonable_packages(self, data, monkeypatch):
        client = MagicMock(post=requests_post)
        monkeypatch.setattr(
            "prefect.engine.cloud.result_handler.Client", MagicMock(return_value=client)
        )
        handler = CloudResultHandler()
        assert isinstance(handler.serialize(data), str)

    def test_cloud_handler_can_interpret_contents_of_standard_uri(self, monkeypatch):
        binary_data = "gASVDQAAAAAAAACMCW15IHNlY3JldJQu"
        client = MagicMock(get=lambda *args, **kwargs: dict(result=binary_data))
        monkeypatch.setattr(
            "prefect.engine.cloud.result_handler.Client", MagicMock(return_value=client)
        )
        handler = CloudResultHandler()
        assert handler.deserialize(uri="http://look-here") == "my secret"

    def test_cloud_handler_handles_empty_buckets(self, monkeypatch):
        binary_data = ""
        client = MagicMock(get=lambda *args, **kwargs: dict(result=binary_data))
        monkeypatch.setattr(
            "prefect.engine.cloud.result_handler.Client", MagicMock(return_value=client)
        )
        handler = CloudResultHandler()
        assert handler.deserialize(uri="http://look-here") is None
