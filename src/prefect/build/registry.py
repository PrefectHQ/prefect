from typing import Dict
from warnings import warn as _warn

import cloudpickle
import xxhash
from cryptography.fernet import Fernet

import prefect
from prefect.core.flow import Flow
from prefect.core.task import Task
from prefect.utilities.json import dumps

REGISTRY = {}


def build_flows() -> dict:
    """
    Build environments for all flows in the registry and produce a metadata dictionary.

    Returns:
        - dict: a dictionary keyed by flow_id and containing metadata for each built flow.
    """
    info = {}
    for flow in REGISTRY.values():
        serialized_flow = flow.serialize()
        environment_key = flow.environment.build(flow)
        info[flow.key()] = dict(
            environment_key=environment_key,
            **serialized_flow
        )

    return info


def register_flow(flow: Flow) -> None:
    """
    Registers a flow by storing it in the registry

    Args:
        - flow (Flow): the flow to register
    """
    if not isinstance(flow, Flow):
        raise TypeError("Expected a Flow; received {}".format(type(flow)))

    if prefect.config.registry.warn_on_duplicate_registration and flow.key() in REGISTRY:
        _warn(
            "Registering this flow overwrote a previously-registered flow "
            "with the same project, name, and version: {}".format(flow)
        )

    REGISTRY[flow.key()] = flow


def load_flow(project, name, version) -> Flow:
    """
    Loads a flow from the registry.

    Args:
        - project (str): the flow's project
        - name (str): the flow's name
        - version (str): the flow's version
    """
    key = (project, name, version)
    if key not in REGISTRY:
        raise KeyError("Flow not found: {}".format(key))
    return REGISTRY[key]


def serialize_registry(registry: dict = None, encryption_key: str = None) -> bytes:
    """
    Serialize the registry to bytes.

    Args:
        - registry (dict): The registry to serialize. If None, the global registry is used.
        - encryption_key (str): A key to use for encrypting the registry. If None
            (the default), then the key in `prefect.config.registry.encryption_key` is used. If
            that key is unavailable, a warning is raised.
    """
    if registry is None:
        registry = REGISTRY
    serialized = cloudpickle.dumps(registry)
    encryption_key = encryption_key or prefect.config.registry.encryption_key
    if not encryption_key:
        _warn(
            "No encryption key provided and none found in "
            "`prefect.config.registry.encryption_key`. The registry will be serialized "
            "but not encrypted."
        )
    else:
        serialized = Fernet(encryption_key).encrypt(serialized)

    return serialized


def load_serialized_registry(serialized: bytes, encryption_key: str = None) -> None:
    """
    Deserialize a serialized registry. This function updates the current registry without
    clearing it first.

    Args:
        - serialized (bytes): a serialized registry
        - encryption_key (str): A key to use for decrypting the registry. If None
            (the default), then the key in `prefect.config.registry.encryption_key` is used. If
            that key is unavailable, deserialization will procede without decryption.
    """
    encryption_key = encryption_key or prefect.config.registry.encryption_key
    if not encryption_key:
        _warn(
            "No encryption key provided and none found in "
            "`prefect.config.registry.encryption_key`. The registry will attempt "
            "unencrypted deserialization."
        )
    else:
        serialized = Fernet(encryption_key).decrypt(serialized)

    REGISTRY.update(cloudpickle.loads(serialized))


def load_serialized_registry_from_path(path: str, encryption_key: str = None) -> None:
    """
    Deserialize a serialized registry from a file. This function updates the current registry without
    clearing it first.

    Args:
        - path (str): a path to a file containing a serialized registry (in bytes)
        - encryption_key (str): A key to use for decrypting the registry. If None
            (the default), then the key in `prefect.config.registry.encryption_key` is used. If
            that key is unavailable, deserialization will procede without decryption.
    """
    with open(path, "rb") as f:
        serialized_registry = f.read()
    load_serialized_registry(serialized_registry, encryption_key=encryption_key)


