"""
Cache policy for per-node dbt orchestration.

Provides DbtNodeCachePolicy (a CachePolicy subclass) and a factory function
that builds policies from DbtNode metadata.  When enabled, unchanged nodes
are skipped on subsequent runs — cache keys incorporate SQL file content,
node config, and upstream cache keys so that changes cascade downstream.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

from prefect.cache_policies import CachePolicy
from prefect.context import TaskRunContext
from prefect.filesystems import WritableFileSystem
from prefect.utilities.hashing import hash_objects, stable_hash
from prefect_dbt.core._manifest import DbtNode

logger = logging.getLogger(__name__)


@dataclass
class DbtNodeCachePolicy(CachePolicy):
    """Cache policy for a single dbt node.

    All data is baked in at construction time (pre-computed hashes) so the
    policy is pickle-safe across process boundaries and does not hold
    references to ``ManifestParser`` or ``Path`` objects.

    Fields:
        node_unique_id: Ensures distinct keys per node.
        file_content_hash: Hash of the source SQL/CSV file (None if missing).
        config_hash: Hash of the node config dict (None if empty).
        full_refresh: Separates full_refresh vs normal cache entries.
        upstream_cache_keys: Sorted upstream node_id → key pairs for
            deterministic hashing.
    """

    node_unique_id: str = ""
    file_content_hash: Optional[str] = None
    config_hash: Optional[str] = None
    full_refresh: bool = False
    upstream_cache_keys: tuple[tuple[str, str], ...] = ()

    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: dict[str, Any],
        flow_parameters: dict[str, Any],
        **kwargs: Any,
    ) -> Optional[str]:
        """Compute a cache key from pre-baked node metadata.

        ``task_ctx``, ``inputs``, and ``flow_parameters`` are ignored — all
        data needed for the key is stored directly on the policy instance.
        """
        return hash_objects(
            self.node_unique_id,
            self.file_content_hash,
            self.config_hash,
            self.full_refresh,
            self.upstream_cache_keys,
        )


def _hash_node_file(node: DbtNode, project_dir: Path) -> Optional[str]:
    """Hash the source file for *node* (SQL for models/snapshots, CSV for seeds).

    Returns ``None`` when the file cannot be located on disk.
    """
    if not node.original_file_path:
        return None

    file_path = project_dir / node.original_file_path
    try:
        content = file_path.read_bytes()
    except (OSError, IOError):
        logger.warning(
            "Could not read source file for %s at %s; "
            "cache key will not reflect file content changes",
            node.unique_id,
            file_path,
        )
        return None

    return stable_hash(content)


def _hash_node_config(node: DbtNode) -> Optional[str]:
    """Hash the config dict for *node*.  Returns ``None`` for empty configs."""
    if not node.config:
        return None
    return hash_objects(node.config)


def build_cache_policy_for_node(
    node: DbtNode,
    project_dir: Path,
    full_refresh: bool,
    upstream_cache_keys: dict[str, str],
    key_storage: Optional[Union[WritableFileSystem, str, Path]] = None,
) -> DbtNodeCachePolicy:
    """Construct a :class:`DbtNodeCachePolicy` for *node*.

    1. Hashes the source file (SQL/CSV) on disk.
    2. Hashes the node config dict.
    3. Sorts upstream keys into a deterministic tuple-of-tuples.
    4. Applies *key_storage* via :meth:`CachePolicy.configure` if provided.
    """

    file_hash = _hash_node_file(node, project_dir)
    config_hash = _hash_node_config(node)
    sorted_upstream = tuple(sorted(upstream_cache_keys.items()))

    policy = DbtNodeCachePolicy(
        node_unique_id=node.unique_id,
        file_content_hash=file_hash,
        config_hash=config_hash,
        full_refresh=full_refresh,
        upstream_cache_keys=sorted_upstream,
    )

    if key_storage is not None:
        policy = policy.configure(key_storage=key_storage)

    return policy
