import datetime
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pydantic
import pytest
import yaml
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from kubernetes_asyncio.client import (
    ApiClient,
    AppsV1Api,
    BatchV1Api,
    Configuration,
    CoreV1Api,
    CustomObjectsApi,
)
from kubernetes_asyncio.config import ConfigException
from kubernetes_asyncio.config.kube_config import list_kube_config_contexts
from prefect_kubernetes.credentials import (
    BaseKubernetesCredentials,
    KubernetesApiKeyCredentials,
    KubernetesClusterConfig,
    KubernetesCredentials,
)

from prefect.blocks.core import InvalidBlockRegistration


@pytest.fixture
def create_temp_self_signed_cert(tmp_path):
    """Create a self signed SSL certificate in temporary files for host
        'localhost'

    Returns a tuple containing the certificate file name and the key
    file name.

    It is the caller's responsibility to delete the files after use
    """
    # create a key pair
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # create a self-signed cert
    name = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Chicago"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Chicago"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "myapp"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "myapp"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ]
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1000)
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=10 * 365))
        .sign(key, hashes.SHA256())
    )

    # Save certificate in temporary file
    (cert_file_fd, cert_file_name) = tempfile.mkstemp(
        suffix=".crt", prefix="cert", dir=tmp_path
    )
    cert_file = os.fdopen(cert_file_fd, "wb")
    cert_file.write(cert.public_bytes(serialization.Encoding.PEM))
    cert_file.close()

    # Save key in temporary file
    (key_file_fd, key_file_name) = tempfile.mkstemp(
        suffix=".key", prefix="cert", dir=tmp_path
    )

    key_file = os.fdopen(key_file_fd, "wb")
    key_file.write(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    key_file.close()

    # Return file names
    yield (cert_file_name, key_file_name)

    os.remove(cert_file_name)
    os.remove(key_file_name)


@pytest.fixture
def config_context(create_temp_self_signed_cert):
    _cert_file, _cert_key = create_temp_self_signed_cert
    CONFIG_CONTENT = f"""
            apiVersion: v1
            clusters:
            - cluster:
                certificate-authority: {_cert_file}
                server: https://kubernetes.docker.internal:6443
              name: docker-desktop
            contexts:
            - context:
                cluster: docker-desktop
                user: docker-desktop
              name: docker-desktop
            current-context: docker-desktop
            kind: Config
            preferences: {{}}
            users:
            - name: docker-desktop
              user:
                  client-certificate: {_cert_file}
                  client-key: {_cert_key}
        """
    return CONFIG_CONTENT


@pytest.fixture
def config_file(tmp_path, config_context) -> Path:
    config_file = tmp_path / "kube_config"

    config_file.write_text(config_context)

    return config_file


@pytest.fixture
def mock_cluster_config(monkeypatch):
    mock = MagicMock()
    # We cannot mock this or the `except` clause will complain
    mock.ConfigException.return_value = ConfigException
    mock.load_kube_config = AsyncMock()
    monkeypatch.setattr("prefect_kubernetes.credentials.config", mock)
    monkeypatch.setattr(
        "prefect_kubernetes.credentials.config.ConfigException", ConfigException
    )
    return mock


class TestCredentials:
    @pytest.mark.parametrize(
        "resource_type,client_type",
        [
            ("apps", AppsV1Api),
            ("batch", BatchV1Api),
            ("core", CoreV1Api),
            ("custom_objects", CustomObjectsApi),
        ],
    )
    async def test_client_return_type(
        self, kubernetes_credentials, resource_type, client_type
    ):
        async with kubernetes_credentials.get_client(resource_type) as client:
            assert isinstance(client, client_type)

    async def test_client_bad_resource_type(self, kubernetes_credentials):
        with pytest.raises(
            ValueError, match="Invalid client type provided 'shoo-ba-daba-doo'"
        ):
            async with kubernetes_credentials.get_client("shoo-ba-daba-doo"):
                pass

    async def test_incluster_config(self, mock_cluster_config):
        kubernetes_credentials = KubernetesCredentials()
        mock_cluster_config.load_incluster_config.return_value = None
        async with kubernetes_credentials.get_client("batch"):
            assert mock_cluster_config.load_incluster_config.called
            assert not mock_cluster_config.load_kube_config.called

    async def test_load_kube_config(self, mock_cluster_config):
        kubernetes_credentials = KubernetesCredentials()
        mock_cluster_config.load_incluster_config.side_effect = ConfigException()
        mock_cluster_config.load_kube_config.return_value = None
        async with kubernetes_credentials.get_client("batch"):
            assert mock_cluster_config.load_incluster_config.called
            assert mock_cluster_config.load_kube_config.called


class TestBaseKubernetesCredentials:
    def test_is_abstract(self):
        with pytest.raises(TypeError):
            BaseKubernetesCredentials()

    def test_subclasses(self):
        assert issubclass(KubernetesCredentials, BaseKubernetesCredentials)
        assert issubclass(KubernetesApiKeyCredentials, BaseKubernetesCredentials)

    async def test_cannot_register_abstract_base(self):
        with pytest.raises(InvalidBlockRegistration):
            await BaseKubernetesCredentials.aregister_type_and_schema()


class TestKubernetesApiKeyCredentials:
    @pytest.mark.parametrize(
        "resource_type,client_type",
        [
            ("apps", AppsV1Api),
            ("batch", BatchV1Api),
            ("core", CoreV1Api),
            ("custom_objects", CustomObjectsApi),
        ],
    )
    async def test_client_return_type(self, resource_type, client_type):
        credentials = KubernetesApiKeyCredentials(
            host="https://k8s.example.com:6443",
            api_key="my-secret-token",
        )
        async with credentials.get_client(resource_type) as client:
            assert isinstance(client, client_type)

    async def test_client_bad_resource_type(self):
        credentials = KubernetesApiKeyCredentials(
            host="https://k8s.example.com:6443",
            api_key="my-secret-token",
        )
        with pytest.raises(
            ValueError, match="Invalid client type provided 'shoo-ba-daba-doo'"
        ):
            async with credentials.get_client("shoo-ba-daba-doo"):
                pass

    async def test_client_configuration_defaults(self):
        credentials = KubernetesApiKeyCredentials(
            host="https://k8s.example.com:6443",
            api_key="my-secret-token",
        )
        async with credentials.get_client("core") as client:
            cfg = client.api_client.configuration
            assert cfg.host == "https://k8s.example.com:6443"
            assert cfg.api_key["BearerToken"] == "my-secret-token"
            assert cfg.api_key_prefix["BearerToken"] == "Bearer"
            assert cfg.verify_ssl is True
            assert cfg.ssl_ca_cert is None
            auth = await cfg.auth_settings()
            assert auth["BearerToken"] == {
                "type": "api_key",
                "in": "header",
                "key": "authorization",
                "value": "Bearer my-secret-token",
            }

    async def test_client_configuration_custom_prefix(self):
        credentials = KubernetesApiKeyCredentials(
            host="https://k8s.example.com:6443",
            api_key="my-secret-token",
            api_key_prefix="Token",
        )
        async with credentials.get_client("core") as client:
            auth = await client.api_client.configuration.auth_settings()
            assert auth["BearerToken"]["value"] == "Token my-secret-token"

    async def test_client_configuration_no_prefix(self):
        credentials = KubernetesApiKeyCredentials(
            host="https://k8s.example.com:6443",
            api_key="Bearer already-prefixed",
            api_key_prefix=None,
        )
        async with credentials.get_client("core") as client:
            cfg = client.api_client.configuration
            assert "BearerToken" not in cfg.api_key_prefix
            auth = await cfg.auth_settings()
            assert auth["BearerToken"]["value"] == "Bearer already-prefixed"

    async def test_client_configuration_no_prefix_clears_inherited_prefix(self):
        custom_config = Configuration()
        custom_config.api_key_prefix["BearerToken"] = "Bearer"
        credentials = KubernetesApiKeyCredentials(
            host="https://k8s.example.com:6443",
            api_key="raw-token",
            api_key_prefix=None,
        )
        async with credentials.get_client(
            "core", configuration=custom_config
        ) as client:
            cfg = client.api_client.configuration
            assert "BearerToken" not in cfg.api_key_prefix
            auth = await cfg.auth_settings()
            assert auth["BearerToken"]["value"] == "raw-token"

    async def test_client_configuration_ssl_options(self, create_temp_self_signed_cert):
        cert_file, _ = create_temp_self_signed_cert
        credentials = KubernetesApiKeyCredentials(
            host="https://k8s.example.com:6443",
            api_key="my-secret-token",
            ssl_ca_cert=cert_file,
            verify_ssl=False,
        )
        async with credentials.get_client("core") as client:
            cfg = client.api_client.configuration
            assert cfg.ssl_ca_cert == cert_file
            assert cfg.verify_ssl is False

    async def test_client_configuration_preserves_passed_configuration(self):
        custom_config = Configuration()
        custom_config.proxy = "http://proxy.example.com:8080"
        credentials = KubernetesApiKeyCredentials(
            host="https://k8s.example.com:6443",
            api_key="my-secret-token",
        )
        async with credentials.get_client(
            "core", configuration=custom_config
        ) as client:
            cfg = client.api_client.configuration
            assert cfg is custom_config
            assert cfg.proxy == "http://proxy.example.com:8080"
            assert cfg.host == "https://k8s.example.com:6443"
            assert cfg.api_key["BearerToken"] == "my-secret-token"

    def test_api_key_is_secret(self):
        credentials = KubernetesApiKeyCredentials(
            host="https://k8s.example.com:6443",
            api_key="super-secret-value",
        )
        assert "super-secret-value" not in repr(credentials)
        assert (
            "api_key"
            in KubernetesApiKeyCredentials.model_json_schema()["secret_fields"]
        )

    async def test_save_and_load_block(self):
        credentials = KubernetesApiKeyCredentials(
            host="https://k8s.example.com:6443",
            api_key="saved-secret-token",
            api_key_prefix="Bearer",
            verify_ssl=False,
        )
        await credentials.save("test-api-key-creds", overwrite=True)

        loaded = await KubernetesApiKeyCredentials.load("test-api-key-creds")
        assert loaded.host == "https://k8s.example.com:6443"
        assert loaded.api_key.get_secret_value() == "saved-secret-token"
        assert loaded.api_key_prefix == "Bearer"
        assert loaded.verify_ssl is False


class TestKubernetesClusterConfig:
    async def test_instantiation_from_file(self, config_file, config_context):
        cluster_config = KubernetesClusterConfig.from_file(path=config_file)

        assert isinstance(cluster_config, KubernetesClusterConfig)
        assert isinstance(cluster_config.config, dict)
        assert isinstance(cluster_config.context_name, str)

        assert cluster_config.config == yaml.safe_load(config_context)
        assert cluster_config.context_name == "docker-desktop"

    async def test_instantiation_from_dict(self, config_file, config_context):
        cluster_config = KubernetesClusterConfig(
            config=yaml.safe_load(config_context),
            context_name="docker-desktop",
        )

        assert isinstance(cluster_config, KubernetesClusterConfig)
        assert isinstance(cluster_config.config, dict)
        assert isinstance(cluster_config.context_name, str)

        assert cluster_config.config == yaml.safe_load(config_context)
        assert cluster_config.context_name == "docker-desktop"

    async def test_instantiation_from_str(self, config_context):
        cluster_config = KubernetesClusterConfig(
            config=config_context, context_name="docker-desktop"
        )

        assert isinstance(cluster_config, KubernetesClusterConfig)
        assert isinstance(cluster_config.config, dict)
        assert isinstance(cluster_config.context_name, str)

        assert cluster_config.config == yaml.safe_load(config_context)
        assert cluster_config.context_name == "docker-desktop"

    async def test_instantiation_from_invalid_str(self):
        with pytest.raises(
            pydantic.ValidationError,
            match="Input should be a valid dictionary",
        ):
            KubernetesClusterConfig(config="foo", context_name="docker-desktop")

    async def test_instantiation_from_file_with_unknown_context_name(self, config_file):
        with pytest.raises(ValueError):
            await KubernetesClusterConfig.from_file(
                path=config_file, context_name="random_not_real"
            )

    async def test_get_api_client(self, config_file):
        cluster_config = KubernetesClusterConfig.from_file(path=config_file)

        api_client = await cluster_config.get_api_client()
        assert isinstance(api_client, ApiClient)

    async def test_configure_client(self, config_file):
        cluster_config = KubernetesClusterConfig.from_file(path=config_file)
        await cluster_config.configure_client()
        context_dict = list_kube_config_contexts(config_file=str(config_file))
        current_context = context_dict[1]["name"]
        assert cluster_config.context_name == current_context
