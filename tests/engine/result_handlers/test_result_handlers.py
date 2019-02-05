import json
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from prefect.client import Client
from prefect.engine.result_handlers import (
    ResultHandler,
    LocalResultHandler,
    JSONResultHandler,
)
from prefect.utilities.configuration import set_temporary_config


class TestJSONHandler:
    def test_json_handler_initializes_with_no_args(self):
        handler = JSONResultHandler()

    @pytest.mark.parametrize("res", [42, "stringy", None])
    def test_json_handler_writes(self, res):
        handler = JSONResultHandler()
        blob = handler.write(res)
        assert isinstance(blob, str)

    @pytest.mark.parametrize("res", [42, "stringy", None])
    def test_json_handler_writes_and_reads(self, res):
        handler = JSONResultHandler()
        final = handler.read(handler.write(res))
        assert final == res

    def test_json_handler_raises_normally(self):
        handler = JSONResultHandler()
        with pytest.raises(TypeError):
            handler.write(type(None))


class TestLocalHandler:
    @pytest.fixture(scope="class")
    def tmp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    def test_local_handler_initializes_with_no_args(self):
        handler = LocalResultHandler()

    def test_local_handler_initializes_with_dir(self):
        handler = LocalResultHandler(dir="/.prefect")
        assert handler.dir == "/.prefect"

    @pytest.mark.parametrize("res", [42, "stringy", None, type(None)])
    def test_local_handler_writes_and_writes_to_dir(self, tmp_dir, res):
        handler = LocalResultHandler(dir=tmp_dir)
        fpath = handler.write(res)
        assert isinstance(fpath, str)
        assert os.path.basename(fpath).startswith("prefect")

        with open(fpath, "rb") as f:
            val = f.read()
        assert isinstance(val, bytes)

    @pytest.mark.parametrize("res", [42, "stringy", None, type(None)])
    def test_local_handler_writes_and_reads(self, tmp_dir, res):
        handler = LocalResultHandler(dir=tmp_dir)
        final = handler.read(handler.write(res))
        assert final == res


def test_result_handlers_must_implement_read_and_write_to_work():
    class MyHandler(ResultHandler):
        pass

    with pytest.raises(TypeError) as exc:
        m = MyHandler()

    assert "abstract methods read, write" in str(exc.value)

    class WriteHandler(ResultHandler):
        def write(self, val):
            pass

    with pytest.raises(TypeError) as exc:
        m = WriteHandler()

    assert "abstract methods read" in str(exc.value)

    class ReadHandler(ResultHandler):
        def read(self, val):
            pass

    with pytest.raises(TypeError) as exc:
        m = ReadHandler()

    assert "abstract methods write" in str(exc.value)
