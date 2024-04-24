from unittest.mock import MagicMock

import pytest
from prefect_docker.host import DockerHost

from prefect.logging import disable_run_logger


@pytest.fixture
def mock_ctx_docker_client(mock_docker_client, monkeypatch) -> MagicMock:
    monkeypatch.setattr(
        "prefect_docker.host._ContextManageableDockerClient", mock_docker_client
    )
    return mock_docker_client


class TestDockerHost:
    @pytest.fixture
    def host_kwargs(self):
        _host_kwargs = dict(
            base_url="unix:///var/run/docker.sock",
            version="1.35",
            max_pool_size=8,
            credstore_env=None,
            client_kwargs={"tls": True},
        )
        return _host_kwargs

    @pytest.fixture
    def docker_host(self, host_kwargs):
        _docker_host = DockerHost(**host_kwargs)
        for key, val in host_kwargs.items():
            assert getattr(_docker_host, key) == val
        return _docker_host

    @pytest.fixture
    def docker_host_from_env(self, host_kwargs):
        host_kwargs.pop("base_url")
        _docker_host = DockerHost(**host_kwargs)
        for key, val in host_kwargs.items():
            assert getattr(_docker_host, key) == val
        return _docker_host

    def test_get_client(self, docker_host, mock_ctx_docker_client: MagicMock):
        with disable_run_logger():
            docker_host.get_client()
            mock_ctx_docker_client.assert_called_once_with(
                base_url="unix:///var/run/docker.sock",
                version="1.35",
                max_pool_size=8,
                tls=True,
            )

    def test_context_managed_get_client(
        self, docker_host, mock_ctx_docker_client: MagicMock
    ):
        with disable_run_logger():
            with docker_host.get_client() as _:
                mock_ctx_docker_client.assert_called_once_with(
                    base_url="unix:///var/run/docker.sock",
                    version="1.35",
                    max_pool_size=8,
                    tls=True,
                )

    def test_get_client_from_env(
        self, docker_host_from_env, mock_docker_client_from_env: MagicMock
    ):
        with disable_run_logger():
            docker_host_from_env.get_client()
            mock_docker_client_from_env.assert_called_once_with(
                version="1.35",
                max_pool_size=8,
                tls=True,
            )

    def test_context_managed_get_client_from_env(
        self, docker_host_from_env, mock_docker_client_from_env: MagicMock
    ):
        with disable_run_logger():
            with docker_host_from_env.get_client() as _:
                mock_docker_client_from_env.assert_called_once_with(
                    version="1.35",
                    max_pool_size=8,
                    tls=True,
                )
