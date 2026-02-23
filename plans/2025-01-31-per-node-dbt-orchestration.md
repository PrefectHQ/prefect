# Per-Node dbt Orchestration

## Overview

Build a new per-node dbt orchestration mode that gives Prefect full control over dbt DAG execution. Instead of running dbt as a single batch operation (letting dbt handle its own concurrency), Prefect will orchestrate each model, seed, snapshot, and test individually.

## Why We're Doing This

The current `PrefectDbtRunner` is **reactive**—it registers callbacks with dbt's internal scheduler and creates Prefect tasks as dbt starts each node. This means:

- **dbt controls execution**: DAG traversal, concurrency, and retry logic are all handled by dbt
- **Limited Prefect integration**: No per-node retries, no per-node caching, no Prefect-native concurrency limits

The new `PrefectDbtOrchestrator` will be **proactive**:

- **Prefect controls execution**: Parse manifest upfront, compute waves, create tasks with proper dependencies
- **Per-node retries**: A failed model retries independently—no "rerun entire DAG"
- **Per-node caching**: Skip unchanged models automatically; changes propagate downstream
- **Prefect-native concurrency**: Use global concurrency limits to protect warehouse resources
- **Full observability**: Each node is a distinct Prefect task with timing, status, and asset lineage

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PrefectDbtOrchestrator                            │
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐  │
│  │ ManifestParser  │───▶│  ExecutionWave  │───▶│  Per-Node/Wave Tasks    │  │
│  │                 │    │   (wave 0..N)   │    │                         │  │
│  │ • Parse JSON    │    │                 │    │ • Retries               │  │
│  │ • Build graph   │    │ • Independent   │    │ • Cache policies        │  │
│  │ • Filter nodes  │    │   nodes in      │    │ • Concurrency limits    │  │
│  │ • Compute waves │    │   parallel      │    │ • Asset tracking        │  │
│  └─────────────────┘    └─────────────────┘    └───────────┬─────────────┘  │
│                                                            │                │
│  ┌─────────────────────────────────────────────────────────▼─────────────┐  │
│  │                          DbtExecutor (Protocol)                       │  │
│  │                                                                       │  │
│  │   ┌─────────────────────┐         ┌─────────────────────────────┐     │  │
│  │   │   DbtCoreExecutor   │         │     DbtCloudExecutor        │     │  │
│  │   │                     │         │                             │     │  │
│  │   │ • dbtRunner.invoke()│         │ • Create ephemeral job      │     │  │
│  │   │ • Local execution   │         │ • Trigger run               │     │  │
│  │   │ • State flags       │         │ • Poll for completion       │     │  │
│  │   └─────────────────────┘         │ • Delete job (cleanup)      │     │  │
│  │                                   └─────────────────────────────┘     │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    Cache System (cross-run by default)                  ││
│  │                                                                         ││
│  │   DbtNodeCachePolicy (key)             Task Decorator (expiration)      ││
│  │   ┌─────────────────────────────┐      ┌─────────────────────────┐      ││
│  │   │ • SQL content hash          │      │ cache_expiration=       │      ││
│  │   │ • Config hash               │      │   timedelta(days=1)     │      ││
│  │   │ • Upstream cache keys       │      │                         │      ││
│  │   │ • NO run ID (cross-run!)    │      │ Or: source freshness    │      ││
│  │   └─────────────────────────────┘      └─────────────────────────┘      ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

### Execution Flow

```
User calls orchestrator.run_build()
            │
            ▼
    ┌───────────────┐
    │ Parse manifest│  (or run dbt parse if missing)
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ Compute waves │  Wave 0: seeds, Wave 1: staging, Wave 2: marts, etc.
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ Apply filters │  select="marts", exclude="stg_legacy_*"
    └───────┬───────┘
            │
            ▼
  ┌─────────┴─────────┐
  │  For each wave:   │
  │                   │
  │  ┌─────────────┐  │     PER_NODE mode:
  │  │ Create tasks│──┼───▶ One task per node with retries/caching
  │  └─────────────┘  │
  │         │         │     PER_WAVE mode:
  │         ▼         │───▶ One dbt invocation with multiple selectors
  │  ┌─────────────┐  │
  │  │Submit/wait  │  │
  │  └─────────────┘  │
  └─────────┬─────────┘
            │
            ▼
    ┌───────────────┐
    │ Return results│  { node_id: { status, result/error } }
    └───────────────┘
```

## Manifest Parsing Strategy

1. **Delegate to dbt for parsing and selection** - Use `dbtRunner` or `dbt ls` for the heavy lifting
2. **Work with JSON artifacts** - Parse `manifest.json` rather than Python classes
3. **Build minimal graph utilities ourselves** - Only what's needed for wave computation

```
┌─────────────────────────────────────────────────────────────────┐
│                    What dbt provides                            │
├─────────────────────────────────────────────────────────────────┤
│  • dbt parse             → Generates manifest.json              │
│  • dbt ls --select ...   → Resolves selectors to node list      │
│  • manifest.json         → Stable JSON schema (versioned)       │
│    - nodes, sources      → All node metadata                    │
│    - parent_map          → Dependency graph (already computed)  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         What we build                           │
├─────────────────────────────────────────────────────────────────┤
│  • ManifestParser        → Parse JSON, extract DbtNode objects  │
│  • Wave computation      → Topological sort into parallel groups│
│  • Ephemeral resolution  → Trace through ephemeral to real deps │
└─────────────────────────────────────────────────────────────────┘
```

### What manifest.json Provides

The `manifest.json` artifact contains everything we need:

```python
{
    "nodes": {
        "model.project.stg_users": {
            "unique_id": "model.project.stg_users",
            "name": "stg_users",
            "resource_type": "model",
            "depends_on": {"nodes": ["source.project.raw.users"]},
            "config": {"materialized": "view", ...},
            ...
        },
        ...
    },
    "sources": {...},
    "parent_map": {  # Dependencies already computed by dbt
        "model.project.stg_users": ["source.project.raw.users"],
        ...
    },
    "child_map": {...}  # Reverse dependencies
}
```

## Interfaces

### Core Classes

```python
@dataclass
class DbtNode:
    """Represents a single dbt node for orchestration.

    Wraps the essential information from dbt's manifest for a model, seed,
    snapshot, or test. Used to track dependencies and determine execution order.
    """
    unique_id: str                              # e.g., "model.analytics.stg_users"
    name: str                                   # e.g., "stg_users"
    resource_type: NodeType                     # Model, Seed, Snapshot, Test
    depends_on: list[str]                       # List of upstream node unique_ids
    materialization: Optional[str]              # "view", "table", "incremental", "ephemeral"
    relation_name: Optional[str]                # Full database relation name
    original_file_path: Optional[str]           # Path to SQL file
    config: dict[str, Any]                      # Node configuration

    @property
    def is_executable(self) -> bool:
        """Return True if this node should be executed (not ephemeral or source)."""
        ...

    @property
    def dbt_selector(self) -> str:
        """Return the dbt selector string for this node."""
        ...


@dataclass
class ExecutionWave:
    """A group of nodes that can be executed in parallel.

    Nodes within a wave have no dependencies on each other—they only depend
    on nodes from previous waves. This enables safe parallel execution.
    """
    nodes: list[DbtNode]
    wave_number: int


class ManifestParser:
    """Parse dbt manifest and construct execution graph.

    Reads manifest.json, extracts executable nodes (excluding ephemeral models
    and sources), resolves transitive dependencies through ephemeral nodes,
    and computes execution waves for parallel scheduling.
    """

    def __init__(self, manifest_path: Path): ...

    def get_executable_nodes(self) -> dict[str, DbtNode]:
        """Extract all executable nodes from manifest.

        Returns dict mapping unique_id -> DbtNode for models, seeds, snapshots, tests.
        Excludes ephemeral models and sources.
        """
        ...

    def compute_execution_waves(self) -> list[ExecutionWave]:
        """Compute execution waves based on DAG dependencies.

        Wave 0: nodes with no dependencies
        Wave 1: nodes depending only on wave 0 nodes
        Wave N: nodes depending only on wave 0..N-1 nodes
        """
        ...

    def filter_nodes(
        self,
        select: Optional[str] = None,
        exclude: Optional[str] = None,
    ) -> dict[str, DbtNode]:
        """Filter nodes based on dbt selector expressions.

        Supports model names, tags (tag:daily), paths (path:models/staging),
        wildcards (stg_*), and graph operators (+model, model+).
        """
        ...

    def get_node_dependencies(self, node_id: str) -> list[str]:
        """Get direct executable dependencies for a node."""
        ...
```

### Executor Protocol

```python
@dataclass
class ExecutionResult:
    """Result from executing a dbt node or wave."""
    success: bool
    node_ids: list[str]
    error: Optional[Exception] = None
    artifacts: Optional[dict[str, Any]] = None


@runtime_checkable
class DbtExecutor(Protocol):
    """Protocol for dbt executors.

    Executors handle the actual invocation of dbt commands. This abstraction
    allows the orchestrator to work with either dbt Core CLI or dbt Cloud.
    """

    def execute_node(
        self,
        node: DbtNode,
        command: str,
        full_refresh: bool = False,
    ) -> ExecutionResult:
        """Execute a single dbt node."""
        ...

    def execute_wave(
        self,
        nodes: list[DbtNode],
        full_refresh: bool = False,
    ) -> ExecutionResult:
        """Execute multiple nodes in a single invocation."""
        ...


class DbtCoreExecutor:
    """Executor using dbt Core CLI via dbtRunner.invoke().

    This is the default executor for local dbt execution. Supports all dbt
    state-based execution flags (--state, --defer, --favor-state).
    """

    def __init__(
        self,
        settings: PrefectDbtSettings,
        threads: Optional[int] = None,
        state_path: Optional[Path] = None,
        defer: bool = False,
        defer_state_path: Optional[Path] = None,
        favor_state: bool = False,
    ): ...


class DbtCloudExecutor:
    """Executor using dbt Cloud ephemeral jobs.

    Creates temporary jobs in dbt Cloud, runs them, and deletes them after
    completion. This enables per-node orchestration for dbt Cloud customers
    without requiring local dbt installation.

    Manifest Resolution:
        The orchestrator needs a manifest to parse the DAG. For dbt Cloud, this
        can come from:
        1. `defer_to_job_id` (recommended) - Downloads manifest.json from the
           specified job's most recent successful run via dbt Cloud API
        2. `manifest_path` on the orchestrator - User provides a local manifest
           (e.g., synced from dbt Cloud or generated locally)

        If neither is provided, the executor will create an ephemeral compile
        job to generate the manifest before orchestration begins.
    """

    def __init__(
        self,
        credentials: DbtCloudCredentials,
        project_id: int,
        environment_id: int,
        job_name_prefix: str = "prefect-orchestrator",
        timeout_seconds: int = 900,
        poll_frequency_seconds: int = 10,
        threads: Optional[int] = None,
        defer_to_job_id: Optional[int] = None,  # Also used to fetch manifest
    ): ...

    def fetch_manifest_from_job(self, job_id: int) -> dict:
        """Fetch manifest.json from a job's latest successful run artifacts.

        Uses: GET /accounts/{account_id}/jobs/{job_id}/artifacts/manifest.json
        """
        ...

    def generate_manifest(self) -> dict:
        """Generate manifest by running an ephemeral dbt compile job.

        Creates a temporary job with `dbt compile`, runs it, downloads the
        manifest from the run artifacts, then deletes the job. Used when no
        defer_to_job_id is configured.
        """
        ...
```

### Cache Policy

```python
class DbtNodeCachePolicy(CachePolicy):
    """Cache policy for dbt nodes based on SQL content and upstream changes.

    Cache key is invalidated when:
    - The node's SQL file content changes
    - The node's configuration changes
    - Any upstream node's cache key changes

    IMPORTANT: This policy does NOT include RUN_ID, enabling cross-run caching.
    Unlike Prefect's DEFAULT policy (INPUTS + TASK_SOURCE + RUN_ID), this policy
    intentionally excludes the run ID so cached results persist across flow runs.

    Cache expiration is configured separately on the task via `cache_expiration`.
    Default is 1 day; can be overridden with source freshness-based expiration.
    """

    def __init__(
        self,
        project_dir: Path,
        manifest_parser: ManifestParser,
        node: DbtNode,
        upstream_cache_keys: Optional[dict[str, str]] = None,
    ): ...

    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: dict[str, Any],
        flow_parameters: dict[str, Any],
        **kwargs: Any,
    ) -> Optional[str]:
        """Compute cache key combining SQL hash, config hash, and upstream keys."""
        ...


def compute_freshness_expiration(
    source_freshness: dict[str, datetime],
    node: DbtNode,
    manifest_parser: ManifestParser,
) -> Optional[timedelta]:
    """Compute cache expiration timedelta based on upstream source freshness.

    This returns a timedelta to be passed to the task's `cache_expiration`
    parameter.

    Strategy: Compute how long until the source is expected to have new data
    based on the freshness configuration (warn_after, error_after thresholds).

    Args:
        source_freshness: Dict mapping source_id to max_loaded_at timestamp
        node: The node to compute expiration for
        manifest_parser: Parser for resolving source dependencies

    Returns:
        Expiration timedelta, or None if no freshness data available
    """
    ...


# Type alias for custom cache policy factories
CachePolicyFactory = Callable[
    [Path, ManifestParser, DbtNode, dict[str, str]],
    CachePolicy
]
```

**Cache expiration is configured on the task.** When creating node tasks, the orchestrator passes `cache_expiration` to the `@task` decorator:

```python
@task(
    name=f"dbt_{command}_{node.name}",
    cache_policy=node_cache_policy,
    cache_expiration=compute_freshness_expiration(...), 
    retries=self.retries,
)
def execute_node():
    ...
```

### Main Orchestrator

```python
class TestStrategy:
    """Test execution strategies."""
    IMMEDIATE = "immediate"  # Run tests immediately after their model (like dbt build)
    DEFERRED = "deferred"    # Run all tests after all models complete
    SKIP = "skip"            # Skip tests entirely


class ExecutionMode:
    """Execution mode strategies."""
    PER_NODE = "per_node"    # One dbt invocation per node (enables retries/caching)
    PER_WAVE = "per_wave"    # One dbt invocation per wave (lower process overhead)


class PrefectDbtOrchestrator:
    """Orchestrates per-node dbt execution with Prefect.

    Provides fine-grained control over dbt DAG execution with:
    - Per-node retries and caching
    - Prefect-native concurrency limits
    - Configurable test strategies
    - Support for both dbt Core and dbt Cloud executors
    - State-based incremental execution for CI/CD
    - Automatic downstream skipping on failure
    """

    def __init__(
        self,
        # dbt Core settings (default executor)
        settings: Optional[PrefectDbtSettings] = None,
        manifest_path: Optional[Path] = None,
        # Concurrency configuration
        concurrency: Optional[Union[str, int]] = None,
        threads: Optional[int] = None,
        # Caching configuration
        enable_caching: bool = True,
        cache_expiration: Optional[timedelta] = timedelta(days=1),  # Default 1 day
        cache_policy_factory: Optional[CachePolicyFactory] = None,
        result_storage: Optional[Union[WritableFileSystem, str, Path]] = None,
        cache_key_storage: Optional[Union[WritableFileSystem, str, Path]] = None,
        use_source_freshness_expiration: bool = False,  # Override default expiration
        # Retry configuration
        retries: int = 2,
        retry_delay_seconds: int = 30,
        # Execution configuration
        test_strategy: str = TestStrategy.IMMEDIATE,
        execution_mode: str = ExecutionMode.PER_NODE,
        # State-based execution
        state_path: Optional[Path] = None,
        defer: bool = False,
        defer_state_path: Optional[Path] = None,
        favor_state: bool = False,
        # Artifact configuration
        create_summary_artifact: bool = True,
        include_compiled_code: bool = False,
        write_run_results: bool = False,  # Write dbt-compatible run_results.json
        # Custom executor
        executor: Optional[DbtExecutor] = None,
    ):
        """Initialize the orchestrator.

        Args:
            settings: PrefectDbtSettings for dbt Core executor
            manifest_path: Override path to manifest.json
            concurrency: Either a string (name of existing Prefect global concurrency
                limit) or int (sets max_workers on ProcessPoolTaskRunner). E.g.,
                "dbt-warehouse" or 4.
            threads: dbt --threads for parallelism within each node
            enable_caching: Whether to enable per-node caching (cross-run by default)
            cache_expiration: How long cached results remain valid (default: 1 day)
            cache_policy_factory: Custom factory for cache policies
            result_storage: Storage for cross-run cache persistence (e.g., "s3-bucket/results")
            cache_key_storage: Storage for cache metadata
            use_source_freshness_expiration: Override cache_expiration with source freshness-based value
            retries: Number of retries per node (per-node mode only)
            retry_delay_seconds: Delay between retries
            test_strategy: When to run tests (immediate/deferred/skip)
            execution_mode: Per-node or per-wave execution
            state_path: Path to state artifacts for comparison (dbt --state)
            defer: Use state for unbuilt dependencies (dbt --defer)
            defer_state_path: Override state path for deferral
            favor_state: Prefer state artifacts over local (dbt --favor-state)
            create_summary_artifact: Create markdown summary artifact at end of run
            include_compiled_code: Include compiled SQL in asset descriptions
            write_run_results: Write dbt-compatible run_results.json for tooling integration
            executor: Custom executor (DbtCoreExecutor or DbtCloudExecutor, default: DbtCoreExecutor)
        """
        ...

    def run_build(
        self,
        select: Optional[str] = None,
        exclude: Optional[str] = None,
        full_refresh: bool = False,
        only_fresh_sources: bool = False,
    ) -> dict[str, Any]:
        """Run dbt build with per-node orchestration.

        Equivalent to `dbt build` but with per-node Prefect tasks.

        Args:
            select: dbt selector expression (e.g., "marts", "tag:daily")
            exclude: dbt exclude expression
            full_refresh: Whether to full-refresh incremental models
            only_fresh_sources: Only run models whose upstream sources have new data

        Returns:
            Dict mapping node_id to execution result:
            {
                "model.analytics.stg_users": {"status": "success", "result": ...},
                "model.analytics.company_summary": {"status": "error", "error": "..."},
                "model.analytics.top_merchants": {"status": "skipped", "reason": "upstream failure"},
            }
        """
        ...
```

## Selector Resolution

To ensure compatibility with dbt's selector semantics (graph operators, tags, paths, etc.), we **delegate selector resolution to dbt** rather than reimplementing it:

```python
def resolve_selection(
    self,
    select: Optional[str] = None,
    exclude: Optional[str] = None,
) -> set[str]:
    """Resolve dbt selectors to a set of node unique_ids.

    Delegates to `dbt ls` to ensure exact compatibility with dbt's
    selector syntax, including graph operators (+model, model+),
    indirect selection, and state-based selectors.
    """
    args = ["ls", "--output", "json", "--resource-type", "all"]
    if select:
        args.extend(["--select", select])
    if exclude:
        args.extend(["--exclude", exclude])

    # Run dbt ls and parse JSON output
    result = self._run_dbt(args)
    return {node["unique_id"] for node in result}
```

**Ephemeral node handling**: The manifest parser traces through ephemeral models to their non-ephemeral dependencies. If model A depends on ephemeral model B which depends on model C, then A's `depends_on` will include C (not B). This ensures execution waves only contain runnable nodes.

## Test Execution Semantics

**TestStrategy.IMMEDIATE** runs each test immediately after its parent model completes:

- A test on `stg_users` runs after `stg_users` succeeds (same wave or next)
- A test spanning multiple models (e.g., relationship test between `stg_users` and `stg_orders`) runs after **all** referenced models complete
- Tests are placed in the earliest wave where all their dependencies are satisfied

**TestStrategy.DEFERRED** collects all tests and runs them in a final phase:

- All models/seeds/snapshots complete first
- Tests run in parallel (respecting concurrency limits)
- Useful when you want faster model execution and can tolerate delayed test feedback

**Test execution uses `dbt test --select <test_unique_id>`**, not `dbt build`, ensuring each test runs independently with proper isolation.

## Failure Semantics

**PER_NODE mode:**
- Each node is an independent Prefect task with its own retries
- If a node fails after all retries, it's marked as failed
- Downstream nodes are marked as "skipped" with reason "upstream failure"
- Other nodes in the same wave continue executing (they're independent)

**PER_WAVE mode:**
- Each wave is a single dbt invocation: `dbt run --select node1 node2 node3`
- If **any** node in the wave fails, the entire wave is marked as failed
- All downstream waves are skipped
- **Partial successes within a wave are not recoverable** - this is an explicit tradeoff for lower overhead

```python
# PER_WAVE failure example:
# Wave 1: [stg_users, stg_orders, stg_products]
# If stg_orders fails, stg_users and stg_products may have succeeded,
# but the entire wave is marked failed and downstream waves are skipped.
```

## Performance Guidance

| Mode | Overhead | Best For |
|------|----------|----------|
| **PER_NODE** | Higher (one dbt invocation per node in a subprocess pool) | Production runs where retries/caching matter, DAGs with flaky nodes |
| **PER_WAVE** | Lower (one dbt invocation per wave, in-process) | CI/CD pipelines, dev iterations, stable DAGs where failures are rare |

**PER_NODE overhead details:**
- Each node is a separate `dbtRunner.invoke()` call in a subprocess. The `ProcessPoolTaskRunner` reuses worker processes across tasks (import cost is paid once per worker, not once per node), but dbt's `adapter_management()` calls `reset_adapters()` on each invoke, so each node still pays manifest parse + adapter registration cost.
- This is the same trade-off made by Astronomer Cosmos's LOCAL execution mode, where each Airflow task runs dbt in a separate worker process for adapter registry isolation.
- Users who want maximum speed without per-node control should use `PrefectDbtRunner` (single `dbt build` with callbacks, analogous to Cosmos's WATCHER mode) or PER_WAVE mode.

**Rules of thumb:**
- Start with PER_WAVE (the default) for speed
- Switch to PER_NODE when you need per-node retries, per-node concurrency control, or fine-grained failure isolation
- PER_WAVE is significantly faster for large DAGs but loses per-node retry granularity
- For CI, PER_WAVE + `state:modified+` selector is typically the fastest option

## Result Object Contract

`run_build()` returns a dict mapping node unique_id to result:

```python
{
    "model.analytics.stg_users": {
        "status": "success",          # "success" | "error" | "skipped" | "cached"
        "timing": {
            "started_at": "2024-01-15T10:30:00Z",
            "completed_at": "2024-01-15T10:30:05Z",
            "duration_seconds": 5.2,
        },
        "invocation": {
            "command": "run",
            "args": ["--select", "model.analytics.stg_users"],
        },
        "rows_affected": 1523,        # If available from dbt
        "cache_key": "abc123...",     # If caching enabled
    },
    "model.analytics.stg_orders": {
        "status": "error",
        "timing": {...},
        "invocation": {...},
        "error": {
            "message": "Database error: relation does not exist",
            "type": "DatabaseError",
        },
    },
    "model.analytics.order_summary": {
        "status": "skipped",
        "reason": "upstream failure",
        "failed_upstream": ["model.analytics.stg_orders"],
    },
    "model.analytics.cached_model": {
        "status": "cached",
        "cache_key": "def456...",
        "cached_at": "2024-01-14T08:00:00Z",
    },
}
```

**Note**: Results are Prefect-native. For dbt tooling compatibility, users can optionally enable `write_run_results=True` to generate a `run_results.json` file in dbt's schema.

## Usage Examples

### Basic Per-Node Orchestration

```python
from pathlib import Path
from prefect import flow
from prefect_dbt import PrefectDbtOrchestrator, PrefectDbtSettings

@flow
def run_dbt_build():
    settings = PrefectDbtSettings(
        project_dir=Path("./my_dbt_project"),
        profiles_dir=Path("~/.dbt"),
    )

    orchestrator = PrefectDbtOrchestrator(
        settings=settings,
        concurrency=4,  # Limit to 4 parallel nodes (ephemeral limit)
    )
    results = orchestrator.run_build()

    # Summarize results
    success = sum(1 for r in results.values() if r["status"] == "success")
    failed = sum(1 for r in results.values() if r["status"] == "error")
    print(f"Completed: {success} succeeded, {failed} failed")

    return results
```

### Production Setup with Caching and Concurrency

```python
from prefect_dbt import PrefectDbtOrchestrator, PrefectDbtSettings, TestStrategy

@flow
def run_production_dbt():
    orchestrator = PrefectDbtOrchestrator(
        settings=PrefectDbtSettings(
            project_dir=Path("./analytics"),
            profiles_dir=Path("./profiles"),
        ),
        # Protect warehouse with concurrency limit
        # Either use existing: concurrency="dbt-warehouse"
        # Or create ephemeral: concurrency=4
        concurrency="dbt-warehouse",
        threads=2,
        # Cross-run caching with S3
        enable_caching=True,
        result_storage="s3-bucket/dbt-results",
        cache_key_storage="s3-bucket/dbt-cache-keys",
        # Retry configuration
        retries=3,
        retry_delay_seconds=60,
        test_strategy=TestStrategy.IMMEDIATE,
    )

    return orchestrator.run_build()
```

### CI/CD Incremental Builds

```python
from prefect_dbt import PrefectDbtOrchestrator, PrefectDbtSettings, ExecutionMode

@flow
def run_ci_incremental():
    """Run only modified models, deferring to production for unchanged ones."""
    orchestrator = PrefectDbtOrchestrator(
        settings=PrefectDbtSettings(project_dir=Path("./analytics")),
        # Point to production artifacts for comparison
        state_path=Path("./prod_artifacts"),
        defer=True,
        # Use per-wave mode for faster CI
        execution_mode=ExecutionMode.PER_WAVE,
    )

    # Only run models that changed and their downstream dependents
    return orchestrator.run_build(select="state:modified+")
```

### dbt Cloud Executor

```python
from prefect_dbt import PrefectDbtOrchestrator, TestStrategy
from prefect_dbt.cloud.executor import DbtCloudExecutor
from prefect_dbt.cloud.credentials import DbtCloudCredentials

@flow
def run_dbt_cloud():
    """Per-node orchestration using dbt Cloud ephemeral jobs."""
    cloud_executor = DbtCloudExecutor(
        credentials=DbtCloudCredentials.load("my-dbt-cloud"),
        project_id=12345,
        environment_id=67890,
        job_name_prefix="prefect-ci",
        # Production job ID - used to:
        # 1. Fetch manifest.json for DAG parsing
        # 2. Defer to production for state comparison
        defer_to_job_id=111,
    )

    orchestrator = PrefectDbtOrchestrator(
        executor=cloud_executor,
        concurrency="dbt-cloud-slots",  # or concurrency=4 for ephemeral limit
        test_strategy=TestStrategy.IMMEDIATE,
    )

    return orchestrator.run_build()
```

### Freshness-Aware Caching

```python
from prefect_dbt import PrefectDbtOrchestrator, PrefectDbtSettings

@flow
def run_on_fresh_data():
    """Only run models whose sources have new data.

    The orchestrator automatically:
    1. Runs `dbt source freshness` to get max_loaded_at timestamps
    2. Computes `cache_expiration` timedelta for each task based on
       source freshness thresholds (warn_after, error_after)
    3. Passes expiration to the task decorator

    This uses Prefect's native task-level cache_expiration parameter,
    keeping the CachePolicy focused only on key computation.
    """
    orchestrator = PrefectDbtOrchestrator(
        settings=PrefectDbtSettings(project_dir=Path("./analytics")),
        state_path=Path("./prod_artifacts"),
        # Compute cache_expiration from source freshness thresholds
        use_source_freshness_expiration=True,
    )

    # Models automatically skip when source data unchanged
    return orchestrator.run_build(only_fresh_sources=True)
```

## Artifacts and Asset Tracking

The orchestrator mirrors the artifact creation behavior of `PrefectDbtRunner`:

### Summary Markdown Artifact

Created at the end of `run_build()` via `create_markdown_artifact()`:

```markdown
## dbt build Task Summary

| Successes | Errors | Failures | Skips | Warnings |
| :-------: | :----: | :------: | :---: | :------: |
|    12     |   1    |    0     |   2   |    1     |

### Unsuccessful Nodes

**stg_transactions**
Type: model
Message: > Database error: relation "raw.transactions" does not exist
Path: models/staging/stg_transactions.sql

### Successful Nodes
stg_users, stg_companies, stg_cards, ...
```

### Per-Node Asset Tracking

For models, seeds, and snapshots with a `relation_name`, the orchestrator uses `MaterializingTask`:

```python
# Asset created from node metadata
asset = Asset(
    key=format_resource_id(adapter_type, node.relation_name),  # e.g., "postgres://db.schema.table"
    properties=AssetProperties(
        name=node.name,
        description=node.description + compiled_code,  # Compiled SQL if enabled
        owners=[owner] if owner else [],               # From node meta.owner
    ),
)

# Task wrapped with MaterializingTask for asset lineage
task = MaterializingTask(
    fn=execute_node,
    assets=[asset],
    asset_deps=upstream_assets,  # Assets from upstream nodes
    materialized_by="dbt",
)
```

Asset metadata (execution details like timing, row counts) is added via `AssetContext.add_asset_metadata()` after successful execution.

## Key Capabilities

| Capability | Description |
|------------|-------------|
| **Per-node retries** | Failed models retry independently (per-node mode) |
| **Cross-run caching** | Cache persists across flow runs (no RUN_ID in key); 1-day default expiration |
| **Freshness-based expiration** | Optionally override expiration using source freshness thresholds |
| **Result storage** | Configure `result_storage` for remote cache persistence (S3, GCS, etc.) |
| **Flexible concurrency** | Use named limits or create ephemeral limits with an int |
| **Two-level concurrency** | Prefect controls parallel nodes; `--threads` controls within-node parallelism |
| **Test strategies** | Run tests immediately, deferred, or skip entirely |
| **Downstream skipping** | When a node fails, downstream dependents are automatically skipped |
| **State-based execution** | `--state`, `--defer`, `--favor-state` for efficient CI/CD |
| **Execution modes** | Per-node (default) for retries/caching; per-wave for lower overhead |
| **Swappable executors** | dbt Core CLI (default) or dbt Cloud ephemeral jobs |
| **Full observability** | Each node is a distinct Prefect task with timing and status |
| **Asset lineage** | Track dependencies in Prefect's asset graph via MaterializingTask |
| **Summary artifact** | Markdown artifact with success/error counts and failure details |

## What We're NOT Doing

1. **Not replacing `PrefectDbtRunner`**: The new mode is additive
2. **Not modifying dbt internals**: We invoke dbt correctly per-node
3. **Not implementing snapshot SCD logic**: dbt handles this
4. **Not implementing custom SQL compilation**: dbt compiles, we execute

## Migration Path

- **Existing users**: Continue using `PrefectDbtRunner` unchanged
- **Opting in**: Use `PrefectDbtOrchestrator` for per-node control
- **Switching**: No data migration needed—just code change
- **Rollback**: Simply switch back to `PrefectDbtRunner`

## Implementation Phases

This implementation is designed to be delivered across multiple PRs, with each phase building on the previous one.

### Phase 1: Core Data Structures and Manifest Parsing ✅

**Status**: Complete — [PR #20561](https://github.com/PrefectHQ/prefect/pull/20561)

**PR Scope**: Foundation classes for representing dbt nodes and parsing manifests.

**Deliverables**:
- `DbtNode` dataclass with all properties
- `ExecutionWave` dataclass
- `ManifestParser` class:
  - Parse `manifest.json` to extract nodes
  - Build dependency graph from `parent_map`
  - Compute execution waves (topological sort)
  - Handle ephemeral node resolution (trace through to real dependencies)
- Unit tests for manifest parsing and wave computation

**Dependencies**: None (foundational)

**Exit Criteria**:
- Can parse a real dbt manifest.json
- Correctly computes execution waves for a multi-layer DAG
- Ephemeral models are excluded and dependencies traced through

---

### Phase 2: Selector Resolution and Node Filtering ✅

**PR Scope**: Integration with dbt's selector system.

**Deliverables**:
- `resolve_selection()` method using `dbt ls`
- `filter_nodes()` method on ManifestParser
- Support for graph operators (`+model`, `model+`)
- Integration tests with selector expressions

**Dependencies**: Phase 1

**Exit Criteria**:
- `select="marts"`, `select="+stg_users"`, `exclude="stg_legacy_*"` all work correctly
- Selection matches what `dbt ls` would return

**Implementation notes**:
- `resolve_selection()` is a standalone function rather than a method on `ManifestParser`, to keep the parser as a pure JSON parser with no dbt CLI dependency.
- `filter_nodes(selected_node_ids)` takes a pre-resolved `set[str]` of IDs rather than raw selector strings. The orchestrator (Phase 4) will wire `resolve_selection` → `filter_nodes` together.
- `compute_execution_waves(nodes)` gained an optional `nodes` parameter so it can accept filtered output directly.
- Added `DbtLsError` exception class for `dbt ls` failures.
- Tests for `resolve_selection` mock `dbtRunner` rather than using a real dbt project (integration tests deferred to Phase 4).

---

### Phase 3: DbtCoreExecutor ✅

**Status**: Complete — [PR #20589](https://github.com/PrefectHQ/prefect/pull/20589)

**PR Scope**: Executor for running dbt commands via dbtRunner.

**Deliverables**:
- `DbtExecutor` protocol definition
- `ExecutionResult` dataclass
- `DbtCoreExecutor` implementation:
  - `execute_node()` for single-node execution
  - `execute_wave()` for batch execution
  - Support for `--state`, `--defer`, `--favor-state` flags
- Unit tests with mocked dbtRunner

**Dependencies**: Phase 1

**Exit Criteria**:
- Can execute a single node via `dbt run --select <node>`
- Can execute multiple nodes in one invocation
- Correctly passes through state-based flags

**Implementation notes**:
- `--full-refresh` is only passed for commands that support it (`run`, `build`, `seed`). Passing `full_refresh=True` to `execute_node(..., command="test")` or `command="snapshot"` silently ignores the flag rather than forwarding an invalid CLI arg.
- `node_ids` in `ExecutionResult` is the union of the requested select list and the keys from actual dbt results. This handles `dbt build` executing additional nodes (e.g. tests attached to selected models) while ensuring every explicitly requested node always appears.
- `_extract_artifacts` guards against `res.result.results` being `None` (not just missing), avoiding a `TypeError` when iterating.
- New symbols are not exported from `prefect_dbt.core.__init__` — the module is experimental and only accessible via the private `prefect_dbt.core._executor` path. Public API exposure deferred to a later phase.

---

### Phase 4: Basic Orchestrator (PER_WAVE mode) ✅

**Status**: Complete — [PR #20591](https://github.com/PrefectHQ/prefect/pull/20591)

**PR Scope**: Minimal viable orchestrator using per-wave execution.

**Deliverables**:
- `PrefectDbtOrchestrator` class (basic version)
- `run_build()` method with PER_WAVE mode only
- Wave-by-wave execution with proper dependencies
- Basic result object structure
- Downstream skipping on wave failure
- Integration tests against DuckDB project

**Dependencies**: Phases 1, 2, 3

**Exit Criteria**:
- Can run a full dbt build with waves executing in order
- Failed wave causes downstream waves to skip
- Returns result dict with status per node

**Implementation notes**:
- **Bugs fixed in earlier phases** — Integration testing exposed three bugs in Phase 2/3 code:
  1. `resolve_selection()` used default `dbt ls` output (selector-format FQNs) instead of unique_ids. Fixed by adding `--output json` and parsing `unique_id` from JSON rows. Defensive parsing handles both `str` and `dict` rows depending on dbt version.
  2. `_extract_artifacts()` failed on dbt-core 1.11 because `RunResult.unique_id` doesn't exist as a direct attribute — it's on `result.node.unique_id`. Added fallback chain: `getattr(result, "unique_id")` → `getattr(result.node, "unique_id")`.
  3. Executor passed `unique_id` strings (e.g. `seed.test_project.customers`) to `--select`, but dbt expects FQN-style selectors. `unique_id` prefixes like `seed.` aren't valid selector syntax.
- **Selector strategy** — `DbtNode.dbt_selector` now returns `path:<original_file_path>` for runnable types (models, seeds, snapshots), which is globally unique across resource types. Tests are excluded from `path:` selection since multiple test nodes share a single YAML schema file. Falls back to dot-joined FQN, then bare node name. This required adding an `fqn` field to `DbtNode`.
- **Separated tracking from selection** — `DbtCoreExecutor._invoke()` now takes separate `node_ids` (for result tracking) and `selectors` (for `--select` CLI args), since unique_ids and dbt selectors are different formats.
- **Settings defensiveness** — `PrefectDbtOrchestrator.__init__` calls `settings.model_copy()` to avoid mutating a caller-provided `PrefectDbtSettings` instance when aligning `target_path` with an explicit `manifest_path`.
- **Target path alignment** — When `manifest_path` is explicitly provided, the orchestrator derives `target_path` from the manifest's parent directory and updates its internal settings copy. This ensures `resolve_selection()` and the executor both reference the same target directory.
- **CI job** — Added a dedicated `run-prefect-dbt-integration-tests` job in `.github/workflows/integration-package-tests.yaml` that installs the `integration` dependency group (`dbt-duckdb`, `duckdb`) and runs `pytest -m integration` across Python 3.10–3.13. The existing test job skips integration tests via `pytest.importorskip` guards.
- **Test project** — Created a minimal dbt project at `tests/dbt_test_project/` with seeds (customers, orders), staging views, an ephemeral intermediate model, and a mart table. This provides a 3-wave execution graph for integration testing.
- New symbols are not exported from `prefect_dbt.core.__init__` — the orchestrator is accessible via the private `prefect_dbt.core._orchestrator` path. Public API exposure deferred to a later phase.

---

### Phase 5: Per-Node Execution Mode ✅

**Status**: Complete — [PR #20608](https://github.com/PrefectHQ/prefect/pull/20608)

**PR Scope**: Add PER_NODE execution with retries.

**Deliverables**:
- `ExecutionMode.PER_NODE` support
- Individual Prefect tasks per node
- Per-node retry logic
- Concurrency limit support (both named and ephemeral)
- Downstream node skipping on individual failure
- Performance comparison tests

**Dependencies**: Phase 4

**Exit Criteria**:
- Each node is a separate Prefect task
- Failed node retries independently
- Concurrency limits respected
- Downstream nodes skip when upstream fails

**Implementation notes**:
- **`ExecutionMode` class** — Added as a simple namespace class (not an enum) with `PER_WAVE` and `PER_NODE` string constants, consistent with the plan's `ExecutionMode` interface.
- **`_NODE_COMMAND` mapping** — Maps `NodeType.Model → "run"`, `NodeType.Seed → "seed"`, `NodeType.Snapshot → "snapshot"`. In PER_NODE mode each node is executed with its specific dbt command rather than `dbt build`.
- **`_DbtNodeError` exception** — Raised inside Prefect task functions to trigger Prefect's built-in retry mechanism. Carries `execution_result`, `timing`, and `invocation` data so the orchestrator can build a proper error result after all retries are exhausted.
- **Process-based execution via `ProcessPoolTaskRunner`** — Each node runs in its own OS process via Prefect's `ProcessPoolTaskRunner`. This gives each subprocess its own dbt adapter registry (`FACTORY` singleton), eliminating the shared mutable state that caused race conditions with dbt's `adapter_management()` context manager. This is the same isolation strategy used by Astronomer Cosmos's LOCAL execution mode, where each Airflow task runs in a separate worker process. The original implementation used threads with `threading.Semaphore` and a monkey-patch of `adapter_management` to prevent `reset_adapters()` from racing across threads. The process approach trades some startup overhead (each subprocess reimports dbt-core, re-parses the manifest, and re-registers adapters) for correctness without patching dbt internals. `ProcessPoolExecutor` reuses worker processes across tasks within a wave, so import cost is paid once per worker, not once per node.
- **Concurrency control** — Integer concurrency values set `max_workers` on the `ProcessPoolTaskRunner`. When no integer is provided, `max_workers` defaults to the size of the largest wave. Named string limits use `prefect.concurrency.sync.concurrency` context manager inside the task function, lazily imported only when needed.
- **Pickle safety** — Since tasks cross process boundaries, all data must be picklable. dbt exceptions often aren't (they carry unpicklable references to dbt internals), so `_DbtNodeError` converts `result.error` to a `RuntimeError(str(...))` before raising. The `DbtCoreExecutor` and its `PrefectDbtSettings` (a Pydantic model) are naturally picklable.
- **Removed `warm_up_manifest()` and `_patch_adapter_management()`** — Both were workarounds for thread-based execution. `warm_up_manifest()` cached the dbt manifest to avoid concurrent `parse_manifest()` calls across threads; `_patch_adapter_management()` replaced dbt's `adapter_management` context manager with a no-op to prevent `reset_adapters()` from clearing adapters used by concurrent threads. Neither is needed with process isolation since each subprocess has its own adapter registry and manifest state.
- **Prefect task creation** — A single `@prefect_task`-decorated `run_dbt_node` function is defined once, then customized per node via `.with_options(name=..., retries=..., retry_delay_seconds=...)`. Tasks are submitted via `runner.submit(node_task, parameters={...})`.
- **Wave-by-wave execution** — Waves are processed sequentially. Within each wave, nodes are submitted concurrently to the process pool. Failed nodes are tracked in a `failed_nodes` set; downstream nodes in later waves check this set and are marked `skipped` with `reason="upstream failure"`.
- **Refactored `run_build()`** — Extracted existing wave logic into `_execute_per_wave()` and added `_execute_per_node()`. `run_build()` dispatches based on `self._execution_mode`.
- **Unit test strategy** — Unit tests use `MagicMock` executors that aren't picklable, so they can't run in real subprocesses. An autouse fixture replaces `ProcessPoolTaskRunner` with `_ThreadDelegatingRunner`, a lightweight stand-in that delegates `runner.submit()` to `task.submit()` (Prefect's default thread-based execution). This lets all existing mock-based tests work unchanged while production code uses real subprocesses.
- **DuckDB integration test isolation** — DuckDB's single-writer file lock prevents concurrent subprocess access to the same `.duckdb` file. PER_WAVE tests (which run first in the session) acquire a file lock in the parent process that persists via dbt's adapter registry. A function-scoped `per_node_dbt_project` fixture copies the session project to a fresh temp directory, rewrites `profiles.yml` to point at a new DuckDB file, and pre-seeds data via `subprocess.run()` (not in-process, which would acquire a parent-process lock). Each PER_NODE test gets its own isolated DuckDB file with no lock conflicts.
- **Postgres concurrency tests** — A separate integration test module (`test_orchestrator_postgres_integration.py`) validates real concurrent execution with `concurrency=4` against a Dockerized Postgres instance. These tests confirm that multiple subprocesses can write concurrently without lock conflicts, validating the production use case that DuckDB can't exercise.
- **Performance comparison tests** — Deferred. DuckDB's single-writer limitation prevents meaningful concurrent execution benchmarks. The Postgres integration tests validate concurrent correctness. Unit tests verify `max_workers` is set correctly.
- **Comparison with existing `PrefectDbtRunner`** — The `PrefectDbtRunner` (and Cosmos's WATCHER mode) use a single `dbtRunner.invoke()` call with callbacks to create Prefect tasks that observe dbt's internal execution. The `PrefectDbtOrchestrator` with PER_NODE mode takes the opposite approach: Prefect controls execution of each node individually, enabling per-node retries and concurrency control that dbt's internal threading doesn't offer. Users who want speed without per-node control already have `PrefectDbtRunner` or PER_WAVE mode.
- New symbols (`ExecutionMode`, `PrefectDbtOrchestrator`) are not exported from `prefect_dbt.core.__init__` — the orchestrator remains accessible via the private `prefect_dbt.core._orchestrator` path. Public API exposure deferred to a later phase.

---

### Phase 6: Cache Policy ✅

**Status**: Complete — [PR #20644](https://github.com/PrefectHQ/prefect/pull/20644)

**PR Scope**: Cross-run caching for dbt nodes.

**Deliverables**:
- `DbtNodeCachePolicy` class
- SQL content hashing
- Config hashing
- Upstream cache key propagation
- Integration with Prefect's cache system
- `cache_key_storage` and `result_storage` configuration
- Tests verifying cache hit/miss behavior

**Dependencies**: Phase 5

**Exit Criteria**:
- Second run with no changes shows cache hits
- Modified SQL invalidates cache for that node and downstream
- Cache persists across flow runs (no RUN_ID in key)

**Implementation notes**:
- **`DbtNodeCachePolicy` is a dataclass, not a class with `__init__`** — The plan's interface showed the policy accepting `project_dir`, `ManifestParser`, and `DbtNode` at construction time and computing hashes lazily in `compute_key()`. The implementation instead pre-computes all hashes at construction via the `build_cache_policy_for_node()` factory, storing only primitive fields (`str`, `bool`, `tuple`) on the dataclass. This makes the policy pickle-safe across process boundaries without holding references to `ManifestParser` or `Path` objects — important since PER_NODE tasks run in subprocesses via `ProcessPoolTaskRunner`.
- **`build_cache_policy_for_node()` factory instead of `CachePolicyFactory` callable** — The plan defined a `CachePolicyFactory` type alias and a `cache_policy_factory` parameter on the orchestrator for custom policy factories. The implementation uses a single `build_cache_policy_for_node()` function in `_cache.py` that the orchestrator calls directly via `_build_cache_options_for_node()`. Custom policy factories were deferred as YAGNI.
- **Eager key computation with `computed_cache_keys` dict** — The plan didn't specify how upstream cache keys would be propagated between nodes. The implementation computes cache keys eagerly in `_build_cache_options_for_node()` (before submitting the task) and stores them in a `computed_cache_keys` dict that accumulates across waves. Each node's upstream keys are looked up from this dict. Failed nodes have their keys removed to prevent stale downstream propagation.
- **`enable_caching` defaults to `False`** — The plan showed `enable_caching: bool = True` with a default 1-day expiration. The implementation defaults to `False` with no expiration, making caching explicitly opt-in. This is safer for users who haven't configured `result_storage` and `cache_key_storage`.
- **No `use_source_freshness_expiration`** — This was always planned for Phase 7 but appeared in the Phase 6 constructor interface in the plan. The implementation cleanly separates Phase 6 (cache policy) from Phase 7 (freshness-based expiration).
- **`key_storage` applied via `CachePolicy.configure()`** — The `build_cache_policy_for_node()` factory calls `policy.configure(key_storage=...)` when `key_storage` is provided, using Prefect's built-in cache policy configuration mechanism rather than a custom storage layer.
- **Integration tests use "drop table" detection** — Since real dbt execution doesn't expose mock call counts, integration tests use a "drop table" strategy: drop a database object between runs, then check whether dbt recreated it (cache miss) or left it absent (cache hit). This required `ThreadPoolTaskRunner` instead of `ProcessPoolTaskRunner` in test fixtures to avoid DuckDB's single-writer file lock across subprocesses.
- **26 unit tests + 5 integration tests** — Unit tests (`test_orchestrator_cache.py`) cover policy determinism, pickle safety, hash helpers, upstream propagation, cascade invalidation, full-refresh bypass, and cross-instance persistence. Integration tests (`test_orchestrator_integration.py::TestPerNodeCachingIntegration`) validate against real DuckDB: cache hits on identical runs, cascade invalidation on SQL changes, full-refresh bypass, cross-instance cache sharing, and a control test with caching disabled.

---

### Phase 7: Source Freshness Integration ✅

**Status**: Complete — [PR #20671](https://github.com/PrefectHQ/prefect/pull/20671)

**PR Scope**: Freshness-aware cache expiration.

**Deliverables**:
- `compute_freshness_expiration()` function
- `use_source_freshness_expiration` option
- `only_fresh_sources` parameter on `run_build()`
- Integration with `dbt source freshness` command
- Tests with mock freshness data

**Dependencies**: Phase 6

**Exit Criteria**:
- Can compute expiration from source freshness thresholds
- `only_fresh_sources=True` skips models with stale sources
- Expiration correctly passed to task decorator

**Deviations from plan**:
- **`run_source_freshness()` checks output file, not return value** — `dbt source freshness` returns `success=False` when sources are stale even though `sources.json` is written successfully, so the implementation checks for the output file rather than the dbtRunner result.
- **`get_source_ancestors()` walks all intermediate nodes, not just ephemerals** — Simpler and more correct since any node between a source and the target should be traversed.
- **Integration tests use `src_*` tables with timestamp casts instead of seed tables directly** — DuckDB `dbt source freshness` requires `loaded_at_field` to be a timestamp, not a date. Seed CSVs produce date columns, so the fixture creates separate `src_customers`/`src_orders` tables with `::timestamp` casts.

---

### Phase 8: Test Strategies ✅

**Status**: Complete — [PR #20743](https://github.com/PrefectHQ/prefect/pull/20743)

**PR Scope**: Configurable test execution behavior.

**Deliverables**:
- `TestStrategy` enum (IMMEDIATE, DEFERRED, SKIP)
- Test placement logic for IMMEDIATE mode
- Deferred test collection and execution
- Tests verifying all three strategies

**Dependencies**: Phase 5

**Exit Criteria**:
- IMMEDIATE: tests run right after their parent model
- DEFERRED: all tests run after all models complete
- SKIP: no tests executed
- Multi-model tests wait for all referenced models

**Deviations from plan**:
- **`TestStrategy` is an `Enum`, not a plain class with string constants** — The plan defined `TestStrategy` as a namespace class (like `ExecutionMode`). The implementation uses `enum.Enum` with string values for type safety and validation. A `__test__ = False` attribute prevents pytest from collecting the class.
- **Default is `SKIP`, not `IMMEDIATE`** — The plan showed `test_strategy: str = TestStrategy.IMMEDIATE` on the orchestrator constructor. The implementation defaults to `TestStrategy.SKIP` for backward compatibility with existing users who never had tests interleaved into orchestrator runs.
- **`NodeType.Unit` support added** — The plan only mentioned `Test` nodes. The implementation adds a `_TEST_TYPES = frozenset({NodeType.Test, NodeType.Unit})` constant to handle both dbt schema/data tests and dbt unit tests.
- **`ManifestParser` gained `get_test_nodes()` and `filter_test_nodes()` methods** — The plan didn't specify manifest parser changes. `get_test_nodes()` returns all test nodes with dependencies resolved through ephemerals. `filter_test_nodes(selected_node_ids, executable_node_ids)` filters tests by user selection and ensures multi-model tests are excluded when any parent model is missing from the executable set.
- **Tests are never cached** — When `enable_caching=True`, test nodes are explicitly excluded from cache policy assignment. Tests always run fresh.
- **Indirect selection suppression in PER_WAVE mode** — `execute_wave()` gained an `indirect_selection` parameter. The orchestrator passes `indirect_selection="empty"` to prevent dbt from automatically including tests when building selected models, giving the orchestrator exclusive control over test scheduling. A fallback retries without the kwarg for legacy executor implementations that don't support the parameter.
- **Kahn's algorithm for IMMEDIATE wave placement** — Rather than custom placement logic, IMMEDIATE mode merges test nodes into the model graph and lets `compute_execution_waves()` (Kahn's algorithm) naturally place each test in the earliest wave where all dependencies are satisfied. Multi-model tests automatically wait for all parent models.
- **DEFERRED computes separate test waves then concatenates** — Test waves are computed independently, renumbered to follow model waves, and appended. Since tests have no inter-dependencies, they all land in a single final wave.

---

### Phase 9: Artifacts and Asset Tracking ✅

**Status**: Complete — [PR #20743](https://github.com/PrefectHQ/prefect/pull/20743)

**PR Scope**: Prefect artifacts and asset lineage.

**Deliverables**:
- Summary markdown artifact creation
- `MaterializingTask` integration for asset lineage
- Asset metadata (timing, row counts)
- `include_compiled_code` option
- `write_run_results` option for dbt-compatible output

**Dependencies**: Phase 5

**Exit Criteria**:
- Summary artifact appears in Prefect UI
- Asset graph shows model dependencies
- Compiled SQL included when enabled
- run_results.json written when enabled

**Deviations from plan**:
- **Dedicated `_artifacts.py` module** — The plan didn't specify a module structure for artifact logic. All artifact helpers (`create_summary_markdown`, `create_run_results_dict`, `write_run_results_json`, `create_asset_for_node`, `get_upstream_assets_for_node`, `get_compiled_code_for_node`) were extracted into a standalone `_artifacts.py` module, keeping `_orchestrator.py` focused on execution logic.
- **No row counts in asset metadata** — The plan listed "Asset metadata (timing, row counts)" as a deliverable. dbt's `RunResult` objects do not expose row counts, so only `status` and `execution_time` are attached via `AssetContext.add_asset_metadata()`.
- **Graceful degradation for artifact creation** — Summary artifact creation is wrapped in a broad `try/except` so API failures (e.g. no active flow run context, network errors) are silently ignored rather than aborting the build.
- **`_build_asset_task()` nested helper** — Asset task construction is factored into a `_build_asset_task()` closure inside `_execute_per_node()`. Non-asset nodes fall back to a single shared `base_task` instance created once per wave loop to avoid redundant `with_options()` calls.
- **Upstream asset resolution traces through ephemeral models** — `get_upstream_assets_for_node()` explicitly walks through ephemeral model dependencies so that lineage reaches the actual materialized upstream relations rather than stopping at the ephemeral boundary.
- **Asset description length clamping** — Descriptions are clamped to Prefect's `MAX_ASSET_DESCRIPTION_LENGTH`. Compiled code (the suffix) is dropped first; if the base description alone still exceeds the limit it is truncated.
- **`relation_name` added to `DbtNodeCachePolicy`** — Cache keys now incorporate `relation_name` so that renaming the materialized relation invalidates the cache. This was a correctness fix surfaced during phase 9 work, not originally scoped to the cache phase.
- **Phase 8 (test strategies) delivered in the same PR** — The test strategy work was implemented on the phase-9 branch and merged together with artifact support in PR #20743.

---

### Phase 10: dbt Cloud Executor ✅

**Status**: Complete — [PR #20784](https://github.com/PrefectHQ/prefect/pull/20784)

**PR Scope**: Execute nodes via dbt Cloud ephemeral jobs.

**Deliverables**:
- `DbtCloudExecutor` class
- Ephemeral job creation and cleanup
- Manifest fetching from job artifacts
- `generate_manifest()` via compile job
- Poll-based job completion monitoring
- Mock API tests + optional live integration test

**Dependencies**: Phase 4 (uses same orchestrator interface)

**Exit Criteria**:
- Can execute nodes via dbt Cloud API
- Ephemeral jobs cleaned up after completion
- Manifest fetched from `defer_to_job_id`
- Works with PrefectDbtOrchestrator via executor protocol

**Deviations from plan**:
- **`get_job_artifact()` added to `DbtCloudAdministrativeClient`** — The plan assumed the Cloud client already had a method for fetching artifacts from a job's most recent successful run. It didn't, so `get_job_artifact(job_id, path)` was added to `clients.py` calling `GET /accounts/{account_id}/jobs/{job_id}/artifacts/{path}`.
- **`get_manifest_path()` uses an isolated `mkdtemp()` directory** — The plan described writing manifest to a temp file. The implementation creates a per-run `tempfile.mkdtemp(prefix="prefect_dbt_")` directory and places `manifest.json` inside it (`target_dir / "manifest.json"`). This is required because `_resolve_target_path()` uses the manifest's parent as the dbt `target_path`; sharing a parent directory (e.g. `/tmp`) across concurrent runs would cause cross-run artifact contamination from fixed-name dbt outputs (`sources.json`, `run_results.json`, etc.).
- **`_poll_run()` timeout uses `time.monotonic()` instead of accumulating poll interval** — The original approach incremented `elapsed += poll_frequency_seconds`, which never advances when `poll_frequency_seconds=0` (used in all tests), causing an infinite loop on any non-terminal run. The implementation tracks wall-clock elapsed time via `time.monotonic()` so the timeout fires correctly regardless of poll interval.
- **`_resolve_manifest_path()` executor branch gained three correctness fixes** — The plan implied a simple `return executor.get_manifest_path()` delegation. The implementation adds: (1) a `callable(getattr(..., None))` guard instead of `hasattr` so non-callable attributes and common test doubles don't falsely trigger the branch; (2) `Path(raw)` wrapping before calling `.is_absolute()` so executors returning a `str` path work without `AttributeError`; (3) relative-path normalization against `project_dir` (mirroring the explicit `manifest_path` branch) so `ManifestParser` and `_resolve_target_path()` both operate on the same absolute path.
- **`settings.target_path` synced after executor manifest resolution** — When the executor provides the manifest, the implementation now also sets `self._settings.target_path = path.parent`, mirroring what `__init__` does for an explicit `manifest_path`. Without this, `_create_artifacts()` and compiled-code lookup still pointed at the old default target directory instead of the executor-provided manifest directory.
- **Live integration test deferred** — The plan listed "optional live integration test" gated by `DBT_CLOUD_API_KEY`. This was not implemented; 59 unit tests cover all executor and orchestrator integration paths with mocked API responses.

---

### Phase Dependency Graph

```
Phase 1 (Manifest Parsing)
    │
    ├──▶ Phase 2 (Selectors)
    │        │
    │        ▼
    └──▶ Phase 3 (DbtCoreExecutor)
             │
             ▼
         Phase 4 (Basic Orchestrator - PER_WAVE)
             │
             ├──▶ Phase 5 (PER_NODE mode)
             │        │
             │        ├──▶ Phase 6 (Cache Policy)
             │        │        │
             │        │        ▼
             │        │    Phase 7 (Source Freshness)
             │        │
             │        ├──▶ Phase 8 (Test Strategies)
             │        │
             │        └──▶ Phase 9 (Artifacts)
             │
             └──▶ Phase 10 (dbt Cloud Executor)
```

### Recommended PR Order

For fastest path to a working MVP:

1. **PR 1**: Phases 1 + 2 (Manifest + Selectors)
2. **PR 2**: Phase 3 (DbtCoreExecutor)
3. **PR 3**: Phase 4 (Basic Orchestrator) — **MVP milestone**
4. **PR 4**: Phase 5 (PER_NODE mode)
5. **PR 5**: Phase 6 (Cache Policy)
6. **PR 6**: Phase 9 (Artifacts) — can parallelize with Phase 7/8
7. **PR 7**: Phase 8 (Test Strategies)
8. **PR 8**: Phase 7 (Source Freshness)
9. **PR 9**: Phase 10 (dbt Cloud Executor)

This order prioritizes getting a working orchestrator (PR 3) that can be tested end-to-end, then layers on advanced features.

## Testing Plan

### Unit Tests

Located in `prefect/src/integrations/prefect-dbt/tests/core/`:

- **test_manifest.py**: ManifestParser correctly parses nodes, computes waves, traces ephemeral dependencies
- **test_cache.py**: Cache key computation, expiration logic, upstream key propagation
- **test_executors.py**: DbtCoreExecutor invocation args, DbtCloudExecutor job lifecycle (mocked API)
- **test_orchestrator.py**: Wave execution, failure propagation, concurrency limit handling

### Integration Tests

Against a DuckDB-based test project:

1. **Full build**: Run orchestrator, verify all nodes execute in correct wave order
2. **Caching**: Run twice, verify cache hits; modify SQL, verify re-execution
3. **Failure propagation**: Inject error in staging model, verify downstream marts are skipped
4. **Test strategies**: Verify IMMEDIATE/DEFERRED/SKIP behavior
5. **Selector resolution**: Test `select="marts"`, `select="+model_name"`, `exclude="stg_*"`
6. **Concurrency**: Create global limit, verify max parallel nodes respected

### dbt Cloud Testing

- **Mock API responses** for unit tests (job create/run/delete, artifact fetch)
- **Optional live test** with test dbt Cloud project (gated by `DBT_CLOUD_API_KEY` env var)
- Verify ephemeral job cleanup happens even on failure (finally block)

### Manual Verification

1. Run `run_analytics_orchestrated()` flow against test project
2. Verify Prefect UI shows individual task runs per node with correct timing
3. Verify asset lineage graph displays model dependencies
4. Verify summary artifact contains success/failure counts and error details
5. Test retry behavior by introducing transient failure (e.g., connection timeout)
