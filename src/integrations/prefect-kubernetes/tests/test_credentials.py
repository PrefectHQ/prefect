import os
import re
import tempfile
from pathlib import Path
from typing import Dict

import pytest
import yaml
from kubernetes_asyncio.client import (
    ApiClient,
    AppsV1Api,
    BatchV1Api,
    CoreV1Api,
    CustomObjectsApi,
)
from kubernetes_asyncio.config.kube_config import list_kube_config_contexts
from OpenSSL import crypto
from prefect_kubernetes.credentials import KubernetesClusterConfig
from pydantic.version import VERSION as PYDANTIC_VERSION

if PYDANTIC_VERSION.startswith("2."):
    import pydantic.v1 as pydantic
else:
    import pydantic


def create_temp_self_signed_cert():
    """Create a self signed SSL certificate in temporary files for host
        'localhost'

    Returns a tuple containing the certificate file name and the key
    file name.

    It is the caller's responsibility to delete the files after use
    """
    # create a key pair
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)

    # create a self-signed cert
    cert = crypto.X509()
    cert.get_subject().C = "US"
    cert.get_subject().ST = "Chicago"
    cert.get_subject().L = "Chicago"
    cert.get_subject().O = "myapp"
    cert.get_subject().OU = "myapp"
    cert.get_subject().CN = "localhost"
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, "sha1")

    # Save certificate in temporary file
    (cert_file_fd, cert_file_name) = tempfile.mkstemp(suffix=".crt", prefix="cert")
    cert_file = os.fdopen(cert_file_fd, "wb")
    cert_file.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    cert_file.close()

    # Save key in temporary file
    (key_file_fd, key_file_name) = tempfile.mkstemp(suffix=".key", prefix="cert")
    key_file = os.fdopen(key_file_fd, "wb")
    key_file.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
    key_file.close()

    # Return file names
    return (cert_file_name, key_file_name)


_cert_file, _cert_key = create_temp_self_signed_cert()

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


@pytest.fixture
def config_file(tmp_path) -> Path:
    config_file = tmp_path / "kube_config"

    config_file.write_text(CONFIG_CONTENT)

    return config_file


@pytest.mark.parametrize(
    "resource_type,client_type",
    [
        ("apps", AppsV1Api),
        ("batch", BatchV1Api),
        ("core", CoreV1Api),
        ("custom_objects", CustomObjectsApi),
    ],
)
async def test_client_return_type(kubernetes_credentials, resource_type, client_type):
    async with kubernetes_credentials.get_client(resource_type) as client:
        assert isinstance(client, client_type)


async def test_client_bad_resource_type(kubernetes_credentials):
    with pytest.raises(
        ValueError, match="Invalid client type provided 'shoo-ba-daba-doo'"
    ):
        async with kubernetes_credentials.get_client("shoo-ba-daba-doo"):
            pass


async def test_instantiation_from_file(config_file):
    cluster_config = await KubernetesClusterConfig.from_file(path=config_file)

    assert isinstance(cluster_config, KubernetesClusterConfig)
    assert isinstance(cluster_config.config, Dict)
    assert isinstance(cluster_config.context_name, str)

    assert cluster_config.config == yaml.safe_load(CONFIG_CONTENT)
    assert cluster_config.context_name == "docker-desktop"


async def test_instantiation_from_dict(config_file):
    cluster_config = KubernetesClusterConfig(
        config=yaml.safe_load(CONFIG_CONTENT), context_name="docker-desktop"
    )

    assert isinstance(cluster_config, KubernetesClusterConfig)
    assert isinstance(cluster_config.config, Dict)
    assert isinstance(cluster_config.context_name, str)

    assert cluster_config.config == yaml.safe_load(CONFIG_CONTENT)
    assert cluster_config.context_name == "docker-desktop"


async def test_instantiation_from_str():
    cluster_config = KubernetesClusterConfig(
        config=CONFIG_CONTENT, context_name="docker-desktop"
    )

    assert isinstance(cluster_config, KubernetesClusterConfig)
    assert isinstance(cluster_config.config, Dict)
    assert isinstance(cluster_config.context_name, str)

    assert cluster_config.config == yaml.safe_load(CONFIG_CONTENT)
    assert cluster_config.context_name == "docker-desktop"


async def test_instantiation_from_invalid_str():
    with pytest.raises(
        pydantic.ValidationError,
        match=re.escape(
            "1 validation error for KubernetesClusterConfig\nconfig\n  value is not a"
            " valid dict (type=type_error.dict)"
        ),
    ):
        KubernetesClusterConfig(config="foo", context_name="docker-desktop")


async def test_instantiation_from_file_with_unknown_context_name(config_file):
    with pytest.raises(ValueError):
        await KubernetesClusterConfig.from_file(
            path=config_file, context_name="random_not_real"
        )


async def test_get_api_client(config_file):
    cluster_config = await KubernetesClusterConfig.from_file(path=config_file)

    api_client = await cluster_config.get_api_client()
    assert isinstance(api_client, ApiClient)


async def test_configure_client(config_file):
    cluster_config = await KubernetesClusterConfig.from_file(path=config_file)
    await cluster_config.configure_client()
    context_dict = list_kube_config_contexts(config_file=str(config_file))
    current_context = context_dict[1]["name"]
    assert cluster_config.context_name == current_context
