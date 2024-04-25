from prefect_ray.context import RemoteOptionsContext, remote_options


def test_remote_options_context():
    input_remote_options = {"num_cpus": 4}
    current_remote_options = RemoteOptionsContext(
        current_remote_options=input_remote_options
    ).current_remote_options
    assert current_remote_options == input_remote_options


def test_remote_options_context_get():
    current_remote_options = RemoteOptionsContext.get().current_remote_options
    assert current_remote_options == {}


def test_remote_options():
    with remote_options(num_cpus=4, num_gpus=None):
        current_remote_options = RemoteOptionsContext.get().current_remote_options
        assert current_remote_options == {"num_cpus": 4, "num_gpus": None}


def test_remote_options_empty():
    with remote_options():
        current_remote_options = RemoteOptionsContext.get().current_remote_options
        assert current_remote_options == {}


def test_remote_options_override():
    with remote_options(num_cpus=2, num_gpus=1):
        with remote_options(num_cpus=4, num_gpus=2):
            current_remote_options = RemoteOptionsContext.get().current_remote_options
            assert current_remote_options == {"num_cpus": 4, "num_gpus": 2}
