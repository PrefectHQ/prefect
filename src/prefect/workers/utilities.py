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


async def get_available_work_pool_types() -> List[str]:
    work_pool_types = set(BaseWorker.get_all_available_worker_types())

    async with get_collections_metadata_client() as collections_client:
        try:
            worker_metadata = await collections_client.read_worker_metadata()
            for collection in worker_metadata.values():
                for worker in collection.values():
                    work_pool_types.add(worker.get("type"))
        except Exception:
            if _is_worker_debug_mode():
                getLogger().warning(
                    "Unable to get worker metadata from the collections registry",
                    exc_info=True,
                )

    return sorted(filter(None, work_pool_types))


async def get_default_base_job_template_for_infrastructure_type(
    infra_type: str,
) -> Optional[Dict[str, Any]]:
    worker_cls = BaseWorker.get_worker_class_from_type(infra_type)
    if worker_cls is not None:
        return deepcopy(worker_cls.get_default_base_job_template())

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
