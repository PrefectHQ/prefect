from prefect.run_configs import LocalRun


def test_no_args():
    config = LocalRun()
    assert config.env is None
    assert config.python_env is None
    assert config.working_dir is None
    assert config.labels == set()


def test_all_args():
    config = LocalRun(
        env={"hello": "world"},
        python_env="conda://prefect",
        working_dir="/path/to/dir",
        labels=["a", "b"],
    )
    assert config.env == {"hello": "world"}
    assert config.python_env == "conda://prefect"
    assert config.working_dir == "/path/to/dir"
    assert config.labels == {"a", "b"}
