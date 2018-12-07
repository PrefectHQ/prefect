import os
import pytest
import tempfile

from prefect.client.result_handlers import LocalResultHandler


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
    def test_local_handler_serializes_and_writes_to_dir(self, tmp_dir, res):
        handler = LocalResultHandler(dir=tmp_dir)
        fpath = handler.serialize(res)
        assert isinstance(fpath, str)
        assert os.path.basename(fpath).startswith("prefect")

        with open(fpath, "rb") as f:
            val = f.read()
        assert isinstance(val, bytes)

    @pytest.mark.parametrize("res", [42, "stringy", None, type(None)])
    def test_local_handler_serializes_and_deserializes(self, tmp_dir, res):
        handler = LocalResultHandler(dir=tmp_dir)
        final = handler.deserialize(handler.serialize(res))
        assert final == res
