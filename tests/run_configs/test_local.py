import os

from prefect.run_configs import LocalRun


def test_no_args():
    config = LocalRun()
    assert config.env is None
    assert config.working_dir is None
    assert config.labels == set()


def test_all_args(tmpdir):
    working_dir = str(tmpdir)
    config = LocalRun(
        env={"hello": "world"}, working_dir=working_dir, labels=["a", "b"],
    )
    assert config.env == {"hello": "world"}
    assert config.working_dir == working_dir
    assert config.labels == {"a", "b"}


def test_working_dir_relpath_to_abspath():
    relpath = os.path.join("local", "path")
    abspath = os.path.abspath(relpath)
    config = LocalRun(working_dir=relpath)
    assert config.working_dir == abspath
