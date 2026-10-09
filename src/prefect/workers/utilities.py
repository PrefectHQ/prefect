from copy import deepcopy
from logging import getLogger
from typing import Any, Dict, List, Optional

from prefect.client.collections import get_collections_metadata_client
from prefect.logging.loggers import get_logger
from prefect.settings import get_current_settings
from prefect.workers.base import BaseWorker


def _is_worker_debug_mode() -> bool:
    settings = get_current_settings()
    return settings.debug_mode or settings.worker.debug_mode


def _collection_name_for_worker(worker_cls: type[BaseWorker[Any, Any, Any]]) -> str:
    """Returns the distribution name of the package a worker class was defined in.

    Worker classes live in a module rooted at their package, so `prefect_armada.worker`
    belongs to `prefect-armada`, matching how the collections registry keys its
    worker metadata.
    """
    return worker_cls.__module__.split(".")[0].replace("_", "-")


def get_locally_installed_worker_metadata() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Builds worker metadata for every worker type installed in this environment.

    The result mirrors the shape of the collections registry's
    `aggregate-worker-metadata` view — collection name, then worker type, then
    metadata — so locally installed workers can be merged into that view. Workers
    from integrations that are not published to the registry (a private or
    in-development collection) are only discoverable this way.
    """
    metadata: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for worker_type in BaseWorker.get_all_available_worker_types():
        worker_cls = BaseWorker.get_worker_class_from_type(worker_type)
        if worker_cls is None:
            continue

        collection_name = _collection_name_for_worker(worker_cls)
        metadata.setdefault(collection_name, {})[worker_type] = {
            "type": worker_type,
            "display_name": worker_cls.get_display_name(),
            "description": worker_cls.get_description(),
            "documentation_url": worker_cls.get_documentation_url(),
            "logo_url": worker_cls.get_logo_url(),
            "install_command": f"pip install {collection_name}",
            "default_base_job_configuration": worker_cls.get_default_base_job_template(),
            "is_beta": False,
        }

    return metadata


async def get_available_work_pool_types() -> List[str]:
    work_pool_types = set(BaseWorker.get_all_available_worker_types())

    async with get_collections_metadata_client() as collections_client:
        try:
            worker_metadata = await collections_client.read_worker_metadata()
            for collection in worker_metadata.values():
                for worker in collection.values():
                    work_pool_types.add(worker.get("type"))
        except Exception:
            # Return only work pool types from the local type registry if
            # the request to the collections registry fails.
            if _is_worker_debug_mode():
                getLogger().warning(
                    "Unable to get worker metadata from the collections registry",
                    exc_info=True,
                )

    return sorted(filter(None, work_pool_types))


async def get_default_base_job_template_for_infrastructure_type(
    infra_type: str,
) -> Optional[Dict[str, Any]]:
    # Attempt to get the default base job template for the worker type
    # from the local type registry first.
    worker_cls = BaseWorker.get_worker_class_from_type(infra_type)
    if worker_cls is not None:
        return deepcopy(worker_cls.get_default_base_job_template())

    # If the worker type is not found in the local type registry, attempt to
    # get the default base job template from the collections registry.
    async with get_collections_metadata_client() as collections_client:
        try:
            worker_metadata = await collections_client.read_worker_metadata()
            for collection in worker_metadata.values():
                for worker in collection.values():
                    if worker.get("type") == infra_type:
                        return worker.get("default_base_job_configuration")
        except Exception:
            if _is_worker_debug_mode():
                get_logger().warning(
                    (
                        "Unable to get default base job template for"
                        f" {infra_type!r} worker type"
                    ),
                    exc_info=True,
                )
        return None
