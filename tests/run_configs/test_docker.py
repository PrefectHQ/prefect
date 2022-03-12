from prefect.run_configs import DockerRun


def test_no_args():
    config = DockerRun()
    assert config.env is None
    assert config.image is None
    assert config.ports is None
    assert config.labels == set()
    assert config.host_config is None


def test_all_args(tmpdir):
    working_dir = str(tmpdir)
    config = DockerRun(
        env={"hello": "world"},
        image="testing",
        labels=["a", "b"],
        ports=[12001],
        host_config={"host": "config"},
    )
    assert config.env == {"hello": "world"}
    assert config.image == "testing"
    assert config.labels == {"a", "b"}
    assert config.ports == [12001]
    assert config.host_config == {"host": "config"}
