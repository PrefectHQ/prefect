"""
Source freshness logic for per-node dbt orchestration.

This module provides:
- SourceFreshnessResult: Parsed result from dbt source freshness
- run_source_freshness: Run `dbt source freshness` and parse results
- get_source_ancestors: Walk the DAG to find source ancestors of a node
- compute_freshness_expiration: Compute cache expiration from upstream freshness
- filter_stale_nodes: Remove nodes with stale upstream sources
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from dbt.artifacts.resources.types import NodeType

from prefect_dbt.core._manifest import DbtNode

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceFreshnessResult:
    """Parsed result for a single source from dbt's sources.json.

    Attributes:
        unique_id: Source unique_id (e.g. "source.project.raw.customers")
        status: Freshness status ("pass", "warn", "error", "runtime error")
        max_loaded_at: When the source was last loaded
        snapshotted_at: When the freshness check ran
        max_loaded_at_time_ago_in_s: Seconds since last load
        warn_after: Threshold for warning status
        error_after: Threshold for error status
    """

    unique_id: str
    status: str
    max_loaded_at: Optional[datetime] = None
    snapshotted_at: Optional[datetime] = None
    max_loaded_at_time_ago_in_s: Optional[float] = None
    warn_after: Optional[timedelta] = None
    error_after: Optional[timedelta] = None


def _period_to_timedelta(count: int, period: str) -> timedelta:
    """Convert a dbt freshness period specification to a timedelta.

    Args:
        count: Number of periods
        period: Period type ("minute", "hour", "day")

    Returns:
        Corresponding timedelta

    Raises:
        ValueError: If the period type is unrecognized
    """
    if period == "minute":
        return timedelta(minutes=count)
    elif period == "hour":
        return timedelta(hours=count)
    elif period == "day":
        return timedelta(days=count)
    raise ValueError(f"Unrecognized freshness period: {period!r}")


def _parse_threshold(threshold_data: Optional[dict[str, Any]]) -> Optional[timedelta]:
    """Parse a dbt freshness threshold dict into a timedelta."""
    if not threshold_data:
        return None
    count = threshold_data.get("count")
    period = threshold_data.get("period")
    if count is None or period is None:
        return None
    return _period_to_timedelta(count, period)


def parse_source_freshness_results(
    sources_json_path: Path,
) -> dict[str, SourceFreshnessResult]:
    """Parse dbt's sources.json into SourceFreshnessResult objects.

    Args:
        sources_json_path: Path to the sources.json file

    Returns:
        Dict mapping source unique_id to SourceFreshnessResult
    """
    with open(sources_json_path) as f:
        data = json.load(f)

    results: dict[str, SourceFreshnessResult] = {}

    for entry in data.get("results", []):
        unique_id = entry.get("unique_id", "")
        status = entry.get("status", "")

        # Parse timestamps
        max_loaded_at = None
        snapshotted_at = None
        max_loaded_at_time_ago_in_s = entry.get("max_loaded_at_time_ago_in_s")

        max_loaded_at_str = entry.get("max_loaded_at")
        if max_loaded_at_str:
            try:
                max_loaded_at = datetime.fromisoformat(
                    max_loaded_at_str.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        snapshotted_at_str = entry.get("snapshotted_at")
        if snapshotted_at_str:
            try:
                snapshotted_at = datetime.fromisoformat(
                    snapshotted_at_str.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        # Parse thresholds from criteria
        criteria = entry.get("criteria", {})
        warn_after = _parse_threshold(criteria.get("warn_after"))
        error_after = _parse_threshold(criteria.get("error_after"))

        results[unique_id] = SourceFreshnessResult(
            unique_id=unique_id,
            status=status,
            max_loaded_at=max_loaded_at,
            snapshotted_at=snapshotted_at,
            max_loaded_at_time_ago_in_s=max_loaded_at_time_ago_in_s,
            warn_after=warn_after,
            error_after=error_after,
        )

    return results


def run_source_freshness(
    settings: Any,
    target_path: Optional[Path] = None,
) -> dict[str, SourceFreshnessResult]:
    """Run `dbt source freshness` and parse the results.

    Returns an empty dict on failure (graceful degradation).

    Args:
        settings: PrefectDbtSettings instance
        target_path: Optional override for the target directory

    Returns:
        Dict mapping source unique_id to SourceFreshnessResult
    """
    from dbt.cli.main import dbtRunner

    output_target = target_path or settings.target_path
    output_path = settings.project_dir / output_target / "sources.json"

    with settings.resolve_profiles_yml() as resolved_profiles_dir:
        args = [
            "source",
            "freshness",
            "--project-dir",
            str(settings.project_dir),
            "--profiles-dir",
            resolved_profiles_dir,
        ]
        if target_path is not None:
            args.extend(["--target-path", str(target_path)])

        try:
            dbtRunner().invoke(args)
        except Exception:
            logger.warning(
                "dbt source freshness command raised an exception",
                exc_info=True,
            )
            return {}

    # dbt source freshness returns success=False when sources are stale
    # but still writes sources.json. Only treat it as failure if the
    # output file was not written.
    if not output_path.exists():
        logger.warning(
            "dbt source freshness did not produce %s; "
            "freshness features will be disabled for this run",
            output_path,
        )
        return {}

    try:
        return parse_source_freshness_results(output_path)
    except Exception:
        logger.warning(
            "Failed to parse source freshness results from %s",
            output_path,
            exc_info=True,
        )
        return {}


def get_source_ancestors(
    node_id: str,
    all_nodes: dict[str, DbtNode],
) -> set[str]:
    """Walk the dependency graph to find all Source ancestors of a node.

    Traces through ephemeral models and all intermediate nodes to find
    every source that feeds into the given node.

    Args:
        node_id: The unique_id of the node to find ancestors for
        all_nodes: All parsed nodes including sources and ephemeral models

    Returns:
        Set of unique_ids for source ancestors
    """
    sources: set[str] = set()
    visited: set[str] = set()

    def _walk(current_id: str) -> None:
        if current_id in visited:
            return
        visited.add(current_id)

        node = all_nodes.get(current_id)
        if node is None:
            return

        if node.resource_type == NodeType.Source:
            sources.add(current_id)
            return

        for dep_id in node.depends_on:
            _walk(dep_id)

    node = all_nodes.get(node_id)
    if node is None:
        return sources

    for dep_id in node.depends_on:
        _walk(dep_id)

    return sources


def compute_freshness_expiration(
    node_id: str,
    all_nodes: dict[str, DbtNode],
    freshness_results: dict[str, SourceFreshnessResult],
) -> Optional[timedelta]:
    """Compute cache expiration for a node based on upstream source freshness.

    For each upstream source with freshness data, computes the remaining
    time before the warn_after threshold is reached. Returns the minimum
    across all sources so the cache expires when the first source goes stale.

    Args:
        node_id: The node to compute expiration for
        all_nodes: All parsed nodes including sources
        freshness_results: Parsed source freshness results

    Returns:
        Minimum remaining time before any upstream source goes stale,
        or None if no freshness data is available
    """
    source_ids = get_source_ancestors(node_id, all_nodes)
    if not source_ids:
        return None

    remaining_times: list[timedelta] = []

    for source_id in source_ids:
        fr = freshness_results.get(source_id)
        if fr is None or fr.warn_after is None:
            continue
        if fr.max_loaded_at_time_ago_in_s is None:
            continue

        time_ago = timedelta(seconds=fr.max_loaded_at_time_ago_in_s)
        remaining = fr.warn_after - time_ago

        # Clamp to zero — if already past threshold, expire immediately
        if remaining < timedelta(0):
            remaining = timedelta(0)

        remaining_times.append(remaining)

    if not remaining_times:
        return None

    return min(remaining_times)


def filter_stale_nodes(
    nodes: dict[str, DbtNode],
    all_nodes: dict[str, DbtNode],
    freshness_results: dict[str, SourceFreshnessResult],
) -> tuple[dict[str, DbtNode], dict[str, Any]]:
    """Remove nodes whose upstream sources are stale.

    A source is considered stale if its freshness status is "error" or
    "runtime error". Nodes that depend (directly or transitively) on a
    stale source are removed, and so are their downstream dependents.

    Args:
        nodes: Executable nodes to filter (from ManifestParser)
        all_nodes: All parsed nodes including sources and ephemeral models
        freshness_results: Parsed source freshness results

    Returns:
        Tuple of (remaining_nodes, skipped_results) where skipped_results
        maps node unique_id to a result dict with status="skipped" and
        a reason indicating the stale source.
    """
    stale_statuses = {"error", "runtime error"}

    # Find all stale source IDs
    stale_sources: set[str] = set()
    for source_id, fr in freshness_results.items():
        if fr.status in stale_statuses:
            stale_sources.add(source_id)

    if not stale_sources:
        return nodes, {}

    # Find nodes with stale upstream sources
    directly_stale: set[str] = set()
    stale_reason: dict[str, str] = {}

    for node_id in nodes:
        ancestors = get_source_ancestors(node_id, all_nodes)
        stale_ancestors = ancestors & stale_sources
        if stale_ancestors:
            directly_stale.add(node_id)
            source_names = sorted(stale_ancestors)
            stale_reason[node_id] = f"stale source: {', '.join(source_names)}"

    # Cascade: remove downstream dependents of stale nodes
    all_stale: set[str] = set(directly_stale)
    cascade_reason: dict[str, str] = {}

    # Build a dependents map for the filtered nodes
    dependents: dict[str, list[str]] = {nid: [] for nid in nodes}
    for nid, node in nodes.items():
        for dep_id in node.depends_on:
            if dep_id in dependents:
                dependents[dep_id].append(nid)

    # BFS to find all downstream nodes
    queue = list(directly_stale)
    while queue:
        current = queue.pop(0)
        for downstream_id in dependents.get(current, []):
            if downstream_id not in all_stale:
                all_stale.add(downstream_id)
                cascade_reason[downstream_id] = "upstream skipped due to stale source"
                queue.append(downstream_id)

    # Build results
    remaining = {nid: node for nid, node in nodes.items() if nid not in all_stale}
    skipped: dict[str, Any] = {}

    for node_id in all_stale:
        reason = stale_reason.get(node_id) or cascade_reason.get(
            node_id, "stale source"
        )
        skipped[node_id] = {
            "status": "skipped",
            "reason": reason,
        }

    return remaining, skipped
