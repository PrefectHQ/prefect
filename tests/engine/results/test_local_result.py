import os
import tempfile

import cloudpickle
import pytest

from prefect import config
from prefect.engine.results import LocalResult


class TestLocalResult:
    @pytest.fixture(scope="class")
    def tmp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    def test_local_result_initializes_with_no_args(self):
        result = LocalResult()
        assert result.dir == os.path.join(config.home_dir, "results")
        assert result.value == None

    def test_local_result_initializes_with_dir(self):
        root_dir = os.path.abspath(os.sep)
        result = LocalResult(dir=root_dir)
        assert result.dir == root_dir

    def test_local_result_writes_using_rendered_template_name(self, tmp_dir):
        result = LocalResult(dir=tmp_dir, filepath="{thing}.txt")
        new_result = result.write("so-much-data", thing=42)
        assert new_result.filepath == "42.txt"
        assert new_result.value == "so-much-data"

    def test_local_result_cleverly_redirects_prefect_defaults(self):
        result = LocalResult(dir=config.home_dir)
        assert result.dir == os.path.join(config.home_dir, "results")

    @pytest.mark.parametrize("res", [42, "stringy", None, type(None)])
    def test_local_result_writes_to_dir(self, tmp_dir, res):
        result = LocalResult(dir=tmp_dir, filepath="test.txt")
        fpath = result.write(res).filepath
        assert isinstance(fpath, str)
        assert fpath == "test.txt"

        with open(fpath, "rb") as f:
            val = f.read()
        assert isinstance(val, bytes)

    @pytest.mark.parametrize("res", [42, "stringy", None, type(None)])
    def test_local_result_writes_and_reads(self, tmp_dir, res):
        result = LocalResult(dir=tmp_dir, filepath="test.txt")
        final = result.read(result.write(res).filepath)
        assert final.value == res

    def test_local_result_is_pickleable(self):
        result = LocalResult(dir="root")
        new = cloudpickle.loads(cloudpickle.dumps(result))
        assert isinstance(new, LocalResult)

    def test_local_result_writes_and_exists(self, tmp_dir):
        result = LocalResult(dir=tmp_dir, filepath="{thing}.txt")
        assert result.exists("43.txt") is False
        new_result = result.write("so-much-data", thing=43)
        assert result.exists("43.txt") is True
