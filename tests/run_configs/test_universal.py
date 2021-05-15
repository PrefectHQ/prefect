from prefect.run_configs import UniversalRun


def test_no_args():
    config = UniversalRun()
    assert config.labels == set()


def test_all_args(tmpdir):
    config = UniversalRun(labels=["a", "b"])
    assert config.labels == {"a", "b"}
