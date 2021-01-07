from prefect.run_configs import DockerRun


def test_no_args():
    config = DockerRun()
    assert config.env is None
    assert config.image is None
    assert config.labels == set()


def test_all_args(tmpdir):
    working_dir = str(tmpdir)
    config = DockerRun(env={"hello": "world"}, image="testing", labels=["a", "b"],)
    assert config.env == {"hello": "world"}
    assert config.image == "testing"
    assert config.labels == {"a", "b"}
