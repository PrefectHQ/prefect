"""
Artifact helpers for the per-node dbt orchestrator.

This module provides:
- create_summary_markdown: Build a markdown summary of orchestrator results
- create_run_results_dict: Build a dbt-compatible run_results dict
- create_asset_for_node: Create a Prefect Asset from a DbtNode
- get_upstream_assets_for_node: Get upstream Asset objects for lineage
- get_compiled_code_for_node: Read compiled SQL for a node
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dbt.version
from dbt.artifacts.resources.types import NodeType

from prefect.assets import Asset, AssetProperties
from prefect.assets.core import MAX_ASSET_DESCRIPTION_LENGTH
from prefect_dbt.core._manifest import DbtNode
from prefect_dbt.utilities import format_resource_id

# Node types that produce database objects and should get assets.
ASSET_NODE_TYPES = frozenset({NodeType.Model, NodeType.Seed, NodeType.Snapshot})

# Node types that can be upstream asset dependencies.
_UPSTREAM_ASSET_TYPES = frozenset(
    {NodeType.Model, NodeType.Seed, NodeType.Snapshot, NodeType.Source}
)


# ------------------------------------------------------------------
# Summary artifact
# ------------------------------------------------------------------


def create_summary_markdown(results: dict[str, Any]) -> str:
    """Build a markdown summary of orchestrator ``run_build()`` results.

    Args:
        results: Dict mapping node unique_id to result dict with a
            ``status`` key (``"success"``, ``"error"``, ``"skipped"``,
            or ``"cached"``).

    Returns:
        Markdown string suitable for ``create_markdown_artifact()``.
    """
    counts: dict[str, int] = {}
    errors: list[tuple[str, dict[str, Any]]] = []
    skipped: list[tuple[str, dict[str, Any]]] = []
    successes: list[str] = []

    for node_id, result in results.items():
        status = result.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1

        if status == "error":
            errors.append((node_id, result))
        elif status == "skipped":
            skipped.append((node_id, result))
        elif status in ("success", "cached"):
            successes.append(node_id)

    total = len(results)

    md = "## dbt build Task Summary\n\n"

    md += "| Successes | Errors | Skipped | Total |\n"
    md += "| :-------: | :----: | :-----: | :---: |\n"
    success_count = counts.get("success", 0) + counts.get("cached", 0)
    md += (
        f"| {success_count} "
        f"| {counts.get('error', 0)} "
        f"| {counts.get('skipped', 0)} "
        f"| {total} |\n"
    )

    if errors:
        md += "\n### Unsuccessful Nodes\n\n"
        for node_id, result in errors:
            name = node_id.rsplit(".", 1)[-1] if "." in node_id else node_id
            resource_type = node_id.split(".", 1)[0] if "." in node_id else "unknown"
            error_info = result.get("error", {})
            message = (
                error_info.get("message", "Unknown error")
                if isinstance(error_info, dict)
                else str(error_info)
            )
            md += f"**{name}**\n\n"
            md += f"Type: {resource_type}\n\n"
            md += f"Message:\n\n> {message}\n\n"

    if skipped:
        md += "\n### Skipped Nodes\n\n"
        for node_id, result in skipped:
            name = node_id.rsplit(".", 1)[-1] if "." in node_id else node_id
            reason = result.get("reason", "unknown reason")
            md += f"* {name} ({reason})\n"
        md += "\n"

    if successes:
        md += "\n### Successful Nodes\n\n"
        for node_id in successes:
            name = node_id.rsplit(".", 1)[-1] if "." in node_id else node_id
            md += f"* {name}\n"
        md += "\n"

    return md


# ------------------------------------------------------------------
# run_results.json
# ------------------------------------------------------------------


def _map_status_to_dbt(status: str) -> str:
    """Map orchestrator status to dbt NodeStatus string."""
    return {
        "success": "success",
        "error": "error",
        "skipped": "skipped",
        "cached": "success",
    }.get(status, status)


def create_run_results_dict(
    results: dict[str, Any],
    elapsed_time: float,
) -> dict[str, Any]:
    """Build a dbt-compatible ``run_results.json`` dict.

    The output schema is compatible with dbt's ``run_results.json`` v6,
    allowing downstream tools (e.g. ``dbt-artifacts``) to consume
    results produced by the orchestrator.

    Args:
        results: Dict mapping node unique_id to result dict.
        elapsed_time: Total elapsed time in seconds.

    Returns:
        Dict in dbt run_results.json schema.
    """
    run_results: list[dict[str, Any]] = []
    for node_id, result in results.items():
        status = result.get("status", "unknown")
        timing_info = result.get("timing", {})
        error_info = result.get("error", {})

        timing_entries: list[dict[str, Any]] = []
        if timing_info.get("started_at"):
            timing_entries.append(
                {
                    "name": "execute",
                    "started_at": timing_info["started_at"],
                    "completed_at": timing_info.get("completed_at", ""),
                }
            )

        rr: dict[str, Any] = {
            "unique_id": node_id,
            "status": _map_status_to_dbt(status),
            "timing": timing_entries,
            "thread_id": "orchestrator",
            "execution_time": timing_info.get(
                "execution_time", timing_info.get("duration_seconds", 0.0)
            ),
            "adapter_response": {},
            "message": error_info.get("message", "") if status == "error" else "OK",
            "failures": None,
            "compiled": None,
            "compiled_code": None,
            "relation_name": None,
            "batch_results": None,
        }

        run_results.append(rr)

    return {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/run-results/v6.json",
            "dbt_version": dbt.version.__version__,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "results": run_results,
        "elapsed_time": elapsed_time,
        "args": {},
    }


def write_run_results_json(
    results: dict[str, Any],
    elapsed_time: float,
    target_dir: Path,
) -> Path:
    """Write a dbt-compatible ``run_results.json`` to *target_dir*.

    Args:
        results: Orchestrator results dict.
        elapsed_time: Total elapsed time in seconds.
        target_dir: Directory to write the file into.

    Returns:
        Path to the written file.
    """
    data = create_run_results_dict(results, elapsed_time)
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / "run_results.json"
    out_path.write_text(json.dumps(data, indent=2))
    return out_path


# ------------------------------------------------------------------
# Asset helpers
# ------------------------------------------------------------------


def create_asset_for_node(
    node: DbtNode,
    adapter_type: str,
    description_suffix: str = "",
) -> Asset:
    """Create a Prefect ``Asset`` from a ``DbtNode``.

    Args:
        node: The DbtNode to create an asset for.  Must have a
            ``relation_name``.
        adapter_type: Database adapter type (e.g. ``"postgres"``).
        description_suffix: Optional suffix appended to the
            description (e.g. compiled SQL block).

    Returns:
        Asset with key derived from *adapter_type* and *relation_name*.

    Raises:
        ValueError: If the node has no ``relation_name``.
    """
    if not node.relation_name:
        raise ValueError(f"Node {node.unique_id} has no relation_name")

    asset_key = format_resource_id(adapter_type, node.relation_name)
    description = (node.description or "") + description_suffix

    if len(description) > MAX_ASSET_DESCRIPTION_LENGTH:
        # Prefer the base description (drop the suffix / compiled code).
        # Truncate if even the base description alone exceeds the limit.
        description = (node.description or "")[:MAX_ASSET_DESCRIPTION_LENGTH]

    owner = node.config.get("meta", {}).get("owner")
    owners = [owner] if owner and isinstance(owner, str) else None

    properties_kwargs: dict[str, Any] = {"name": node.name}

    if description:
        properties_kwargs["description"] = description

    if owners:
        properties_kwargs["owners"] = owners

    return Asset(
        key=asset_key,
        properties=AssetProperties(**properties_kwargs),
    )


def get_upstream_assets_for_node(
    node: DbtNode,
    all_nodes: dict[str, DbtNode],
    adapter_type: str,
) -> list[Asset]:
    """Get upstream ``Asset`` objects for lineage tracking.

    Returns assets for upstream nodes (models, seeds, snapshots,
    sources) that have a ``relation_name``.  Ephemeral models are
    traversed recursively so that sources or models behind them are
    still included.

    Args:
        node: The node to find upstream assets for.
        all_nodes: All parsed nodes including sources.
        adapter_type: Database adapter type.

    Returns:
        List of upstream ``Asset`` objects.
    """
    # Collect asset-eligible dep IDs by walking through ephemerals.
    # The resolved node's depends_on may have had sources stripped
    # during dependency resolution, so start from the original
    # (unresolved) node when available.
    original_node = all_nodes.get(node.unique_id)
    start_deps: set[str] = set(node.depends_on)
    if original_node is not None:
        start_deps |= set(original_node.depends_on)

    collected: list[str] = []
    visited: set[str] = set()

    def _walk(dep_id: str) -> None:
        if dep_id in visited:
            return
        visited.add(dep_id)

        dep_node = all_nodes.get(dep_id)
        if dep_node is None:
            return

        # Trace through ephemeral models to their dependencies.
        if dep_node.materialization == "ephemeral":
            for nested_dep in dep_node.depends_on:
                _walk(nested_dep)
            return

        if dep_node.resource_type in _UPSTREAM_ASSET_TYPES and dep_node.relation_name:
            collected.append(dep_id)

    for dep_id in start_deps:
        _walk(dep_id)

    assets: list[Asset] = []
    for dep_id in collected:
        dep_node = all_nodes[dep_id]
        asset_key = format_resource_id(adapter_type, dep_node.relation_name)
        assets.append(
            Asset(
                key=asset_key,
                properties=AssetProperties(name=dep_node.name),
            )
        )
    return assets


def get_compiled_code_for_node(
    node: DbtNode,
    project_dir: Path,
    target_path: Path,
    project_name: str,
) -> str:
    """Get compiled SQL formatted for inclusion in an asset description.

    Checks the node's ``compiled_code`` field first (populated by
    ``dbt compile``), then falls back to reading from disk.

    Args:
        node: The DbtNode.
        project_dir: dbt project directory.
        target_path: dbt target path (e.g. ``Path("target")``).
        project_name: dbt project name from manifest metadata.

    Returns:
        Formatted markdown code block, or empty string if unavailable.
    """
    code = node.compiled_code

    if not code and node.original_file_path:
        compiled_path = (
            project_dir
            / target_path
            / "compiled"
            / project_name
            / node.original_file_path
        )
        if compiled_path.exists():
            code = compiled_path.read_text()

    if not code:
        return ""

    description = f"\n### Compiled code\n```sql\n{code.strip()}\n```"

    if len(description) > MAX_ASSET_DESCRIPTION_LENGTH:
        description = (
            "\n### Compiled code\n"
            "Compiled code was omitted because it exceeded the maximum "
            f"asset description length of {MAX_ASSET_DESCRIPTION_LENGTH} characters."
        )

    return description
