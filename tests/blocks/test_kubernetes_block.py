import base64
import re
from pathlib import Path
from typing import Dict

import pydantic
import pytest
import yaml
from kubernetes.client import ApiClient
from kubernetes.config.kube_config import list_kube_config_contexts

from prefect.blocks.kubernetes import KubernetesClusterConfig

sample_base64_string = base64.b64encode(b"hello marvin from the other side")

CONFIG_CONTENT = f"""
    apiVersion: v1
    clusters:
    - cluster:
        certificate-authority-data: {sample_base64_string}
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
          client-certificate-data: {sample_base64_string}
          client-key-data: {sample_base64_string}
"""


@pytest.fixture
def config_file(tmp_path) -> Path:
    config_file = tmp_path / "kube_config"

    config_file.write_text(CONFIG_CONTENT)

    return config_file


async def test_instantiation_from_file(config_file):
    cluster_config = KubernetesClusterConfig.from_file(path=config_file)

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
        KubernetesClusterConfig.from_file(
            path=config_file, context_name="random_not_real"
        )


async def test_get_api_client(config_file):
    cluster_config = KubernetesClusterConfig.from_file(path=config_file)
    api_client = cluster_config.get_api_client()
    assert isinstance(api_client, ApiClient)


async def test_configure_client(config_file):
    cluster_config = KubernetesClusterConfig.from_file(path=config_file)
    cluster_config.configure_client()
    context_dict = list_kube_config_contexts(config_file=str(config_file))
    current_context = context_dict[1]["name"]
    assert cluster_config.context_name == current_context
