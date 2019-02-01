import json
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from prefect.client import Client
from prefect.engine.result_serializers import LocalResultSerializer
from prefect.utilities.configuration import set_temporary_config


def requests_post(*args, result=None, **kwargs):
    return dict(uri=json.dumps(result))


class TestLocalHandler:
    @pytest.fixture(scope="class")
    def tmp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    def test_local_handler_initializes_with_no_args(self):
        handler = LocalResultSerializer()

    def test_local_handler_initializes_with_dir(self):
        handler = LocalResultSerializer(dir="/.prefect")
        assert handler.dir == "/.prefect"

    @pytest.mark.parametrize("res", [42, "stringy", None, type(None)])
    def test_local_handler_serializes_and_writes_to_dir(self, tmp_dir, res):
        handler = LocalResultSerializer(dir=tmp_dir)
        fpath = handler.serialize(res)
        assert isinstance(fpath, str)
        assert os.path.basename(fpath).startswith("prefect")

        with open(fpath, "rb") as f:
            val = f.read()
        assert isinstance(val, bytes)

    @pytest.mark.parametrize("res", [42, "stringy", None, type(None)])
    def test_local_handler_serializes_and_deserializes(self, tmp_dir, res):
        handler = LocalResultSerializer(dir=tmp_dir)
        final = handler.deserialize(handler.serialize(res))
        assert final == res
