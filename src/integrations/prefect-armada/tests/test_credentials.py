from pathlib import Path

import grpc
import pytest
from armada_client.asyncio_client import ArmadaAsyncIOClient
from armada_client.client import ArmadaClient
from prefect_armada.credentials import (
    ArmadaClusterConfig,
    ArmadaCredentials,
    _BasicAuth,
    _BearerAuth,
)


class TestArmadaClusterConfig:
    def test_defaults(self):
        config = ArmadaClusterConfig()
        assert config.host == "localhost"
        assert config.port == 50051
        assert config.disable_ssl is False
        assert config.target == "localhost:50051"

    def test_binoculars_target_defaults_to_the_armada_host(self):
        config = ArmadaClusterConfig(host="armada.example.com")
        assert config.binoculars_target == "armada.example.com:50053"

    def test_binoculars_target_can_be_overridden(self):
        config = ArmadaClusterConfig(
            host="armada.example.com",
            binoculars_host="binoculars.example.com",
            binoculars_port=50054,
        )
        assert config.binoculars_target == "binoculars.example.com:50054"

    def test_from_env_reads_prefect_settings(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_ARMADA_CONNECTION_HOST", "armada.example.com"
        )
        monkeypatch.setenv("PREFECT_INTEGRATIONS_ARMADA_CONNECTION_PORT", "50055")
        monkeypatch.setenv("PREFECT_INTEGRATIONS_ARMADA_CONNECTION_DISABLE_SSL", "true")

        config = ArmadaClusterConfig.from_env()

        assert config.target == "armada.example.com:50055"
        assert config.disable_ssl is True

    def test_from_env_reads_armada_tooling_variables(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("ARMADA_SERVER", "armada.example.com")
        monkeypatch.setenv("ARMADA_PORT", "50056")

        config = ArmadaClusterConfig.from_env()

        assert config.target == "armada.example.com:50056"

    def test_channel_options_include_keepalive(self):
        config = ArmadaClusterConfig(channel_options={"grpc.max_metadata_size": 1024})
        options = dict(config.get_channel_options())

        assert options["grpc.keepalive_time_ms"] == 30000
        assert options["grpc.max_metadata_size"] == 1024

    def test_channel_options_can_omit_keepalive(self):
        config = ArmadaClusterConfig(add_grpc_keepalive=False)
        assert config.get_channel_options() == []

    def test_insecure_channel_when_ssl_disabled_and_unauthenticated(self):
        config = ArmadaClusterConfig(disable_ssl=True)
        assert config.get_channel_credentials() is None

    def test_credentials_are_carried_over_an_insecure_endpoint(self):
        config = ArmadaClusterConfig(disable_ssl=True)
        call_credentials = grpc.metadata_call_credentials(_BearerAuth("token"))

        credentials = config.get_channel_credentials(call_credentials)

        assert isinstance(credentials, grpc.ChannelCredentials)

    def test_ssl_channel_credentials_by_default(self):
        config = ArmadaClusterConfig()
        assert isinstance(config.get_channel_credentials(), grpc.ChannelCredentials)

    def test_ssl_channel_credentials_with_root_certificates(self):
        config = ArmadaClusterConfig(
            root_certificates="-----BEGIN CERTIFICATE-----\nnot-a-real-cert\n"
        )
        assert isinstance(config.get_channel_credentials(), grpc.ChannelCredentials)

    def test_root_certificates_are_read_from_a_path(self, tmp_path: Path):
        pem = "-----BEGIN CERTIFICATE-----\nfrom-a-file\n"
        ca_file = tmp_path / "ca.crt"
        ca_file.write_text(pem)

        config = ArmadaClusterConfig(root_certificates_path=ca_file)

        assert config._resolve_root_certificates() == pem.encode()
        assert isinstance(config.get_channel_credentials(), grpc.ChannelCredentials)

    def test_inline_root_certificates_take_precedence_over_a_path(self, tmp_path: Path):
        ca_file = tmp_path / "ca.crt"
        ca_file.write_text("-----BEGIN CERTIFICATE-----\nfrom-a-file\n")

        config = ArmadaClusterConfig(
            root_certificates="-----BEGIN CERTIFICATE-----\ninline\n",
            root_certificates_path=ca_file,
        )

        assert config._resolve_root_certificates() == (
            b"-----BEGIN CERTIFICATE-----\ninline\n"
        )

    def test_default_roots_are_used_when_no_certificates_are_configured(self):
        assert ArmadaClusterConfig()._resolve_root_certificates() is None

    def test_a_missing_root_certificates_file_raises(self, tmp_path: Path):
        config = ArmadaClusterConfig(root_certificates_path=tmp_path / "absent.crt")

        with pytest.raises(ValueError, match="Could not read Armada root certificates"):
            config.get_channel_credentials()

    def test_root_certificates_path_is_ignored_when_ssl_is_disabled(
        self, tmp_path: Path
    ):
        # A stale path must not break a plaintext connection, since the file is
        # never needed for one.
        config = ArmadaClusterConfig(
            disable_ssl=True, root_certificates_path=tmp_path / "absent.crt"
        )

        assert config.get_channel_credentials() is None

    def test_from_env_reads_root_certificates_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        ca_file = tmp_path / "ca.crt"
        ca_file.write_text("-----BEGIN CERTIFICATE-----\nfrom-env\n")
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_ARMADA_CONNECTION_ROOT_CERTIFICATES_PATH",
            str(ca_file),
        )

        config = ArmadaClusterConfig.from_env()

        assert config.root_certificates_path == ca_file
        assert config._resolve_root_certificates() == (
            b"-----BEGIN CERTIFICATE-----\nfrom-env\n"
        )


class TestAuthMetadataPlugins:
    def test_bearer_auth_sends_the_token_verbatim(self):
        captured = {}

        def callback(metadata, error):
            captured["metadata"] = metadata
            captured["error"] = error

        _BearerAuth("Bearer abc123")(None, callback)

        assert captured["metadata"] == (("authorization", "Bearer abc123"),)
        assert captured["error"] is None

    def test_basic_auth_base64_encodes_the_credentials(self):
        captured = {}

        def callback(metadata, error):
            captured["metadata"] = metadata

        _BasicAuth("user", "pass")(None, callback)

        # base64 of "user:pass"
        assert captured["metadata"] == (("authorization", "basic dXNlcjpwYXNz"),)


class TestArmadaCredentials:
    def test_cluster_config_falls_back_to_the_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_ARMADA_CONNECTION_HOST", "armada.example.com"
        )
        credentials = ArmadaCredentials()

        assert credentials.get_cluster_config().host == "armada.example.com"

    def test_cluster_config_is_used_when_provided(self, armada_cluster_config):
        credentials = ArmadaCredentials(cluster_config=armada_cluster_config)
        assert credentials.get_cluster_config() is armada_cluster_config

    def test_no_call_credentials_without_auth(self):
        assert ArmadaCredentials().get_call_credentials() is None

    def test_call_credentials_from_a_token(self):
        credentials = ArmadaCredentials(token="Bearer abc123")
        assert isinstance(credentials.get_call_credentials(), grpc.CallCredentials)

    def test_call_credentials_from_basic_auth(self):
        credentials = ArmadaCredentials(username="user", password="pass")
        assert isinstance(credentials.get_call_credentials(), grpc.CallCredentials)

    def test_call_credentials_require_both_username_and_password(self):
        assert ArmadaCredentials(username="user").get_call_credentials() is None

    def test_call_credentials_from_settings(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("PREFECT_INTEGRATIONS_ARMADA_CONNECTION_TOKEN", "abc123")
        assert isinstance(
            ArmadaCredentials().get_call_credentials(), grpc.CallCredentials
        )

    async def test_get_client_returns_an_async_client(self, armada_credentials):
        async with armada_credentials.get_client() as client:
            assert isinstance(client, ArmadaAsyncIOClient)
            assert client.event_timeout.total_seconds() == 900

    def test_get_sync_client_returns_a_sync_client(self, armada_credentials):
        with armada_credentials.get_sync_client() as client:
            assert isinstance(client, ArmadaClient)

    def test_get_binoculars_client_targets_the_log_service(self, armada_credentials):
        with armada_credentials.get_binoculars_client() as client:
            assert client.binoculars_stub is not None
