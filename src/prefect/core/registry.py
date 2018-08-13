from typing import Dict, Iterable
from warnings import warn as _warn

import cloudpickle
import xxhash
from cryptography.fernet import Fernet

import prefect
from prefect.core.flow import Flow
from prefect.core.task import Task
from prefect.utilities.json import dumps

REGISTRY = {}


def register_flow(flow: Flow) -> None:
    """
    Registers a flow by storing it in the registry

    Args:
        - flow (Flow): the flow to register
    """

    if any(flow.key() == f.key() for f in REGISTRY.values()):
        _warn(
            "The registered flow has the same key {} as an already-registered flow.".format(
                flow.key()
            )
        )

    if not isinstance(flow, Flow):
        raise TypeError("Expected a Flow; received {}".format(type(flow)))
    REGISTRY[flow.id] = flow


def build_flows() -> dict:
    """
    Build environments for all flows in the registry and produce a metadata dictionary.

    Returns:
        - dict: a dictionary keyed by flow.id and containing the serialized version of each
            flow.
    """
    return {flow.id: flow.serialize() for flow in REGISTRY.values()}


def load_flow(id: str) -> Flow:
    """
    Loads a flow from the registry.

    Args:
        - id (str): the flow's id
    """
    if id not in REGISTRY:
        raise ValueError("Flow not found: {}".format(id))
    return REGISTRY[id]


def serialize_registry(
    include_ids: Iterable = None, encryption_key: str = None
) -> bytes:
    """
    Serialize the registry to bytes.

    Args:
        - include_ids (iterable): A iterable of flow IDs to include. If None, all IDs are
            included.
        - encryption_key (str): A key to use for encrypting the registry. If None
            (the default), then the key in `prefect.config.registry.encryption_key` is
            used. If that key is unavailable, a warning is raised.
    """
    if include_ids:
        registry = {k: v for k, v in REGISTRY.items() if k in include_ids}
    else:
        registry = REGISTRY.copy()
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
            (the default), then the key in `prefect.config.registry.encryption_key`
            is used. If that key is unavailable, deserialization will procede without
            decryption.
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
    Deserialize a serialized registry from a file. This function updates the current
    registry without clearing it first.

    Args:
        - path (str): a path to a file containing a serialized registry (in bytes)
        - encryption_key (str): A key to use for decrypting the registry. If None
            (the default), then the key in `prefect.config.registry.encryption_key`
            is used. If that key is unavailable, deserialization will procede without
            decryption.
    """
    with open(path, "rb") as f:
        serialized_registry = f.read()
    load_serialized_registry(serialized_registry, encryption_key=encryption_key)
