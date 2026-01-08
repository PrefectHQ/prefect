# Custom Deployment SDKs

## Goal

Create a CLI command that generates a typed Python SDK from workspace deployments, enabling:
- **IDE autocomplete** for discovering flows and deployments
- **Static type checking** for parameters and job variables
- **Reduced runtime errors** by catching type mismatches before execution

## User Experience

**Before** (current state):
```python
from prefect.deployments import run_deployment

# No autocomplete, no type checking, runtime errors for typos
run_deployment(
    name="my-etl-flow/production",  # Easy to typo
    parameters={"sorce": "s3://bucket"},  # Typo not caught until runtime  # codespell:ignore sorce
)
```

**After** (with generated SDK):
```python
from my_sdk import deployments

# IDE autocomplete, type checking, errors caught immediately
deployments.from_name("my-etl-flow/production").with_options(
    timeout=60,                              # Infrastructure options via method
    job_variables={"memory": "8Gi"},         # Typed based on work pool schema
).run(
    source="s3://bucket",                    # Flow params are direct kwargs
    batch_size=100,                          # Typos caught by type checker
)
```

**Type safety**: The `from_name()` method uses `@overload` decorators so each deployment name returns the correctly-typed class with its specific parameters.

## CLI Interface

```bash
prefect sdk generate --output ./my_sdk.py [--flow NAME] [--deployment NAME]
```

**Options:**
| Flag | Description |
|------|-------------|
| `--output`, `-o` | Output file path (required) |
| `--flow`, `-f` | Filter to specific flow (multiple allowed) |
| `--deployment`, `-d` | Filter to specific deployment (multiple allowed) |

## What Gets Generated

The SDK file contains:
1. **`DeploymentName` Literal type** - All deployment names for autocomplete: `Literal["flow/deploy", ...]`
2. **Per-work-pool TypedDicts** - `{WorkPoolName}JobVariables` for typed job_variables
3. **Class for each deployment** - With `with_options()`, `run()`, and `run_async()` methods
4. **`deployments` namespace** - With `from_name()` method using `@overload` for type-safe dispatch

**Usage**: `deployments.from_name("my-etl-flow/production").with_options(timeout=60).run(source="s3://...")`

**Important**: All type information comes from **server-side metadata** (JSON Schema stored with deployments and work pools). The generator does not inspect flow source code—it works entirely from the Prefect API.

## Architecture

```
Public Interface (CLI only)
└── prefect sdk generate

Private Implementation (src/prefect/_sdk/)
├── Schema conversion (JSON Schema → TypedDict)
├── Name utilities (safe Python identifiers)
├── Data models (internal representation)
├── API fetching (deployment/work pool data)
├── Template rendering (Jinja2)
└── Generator orchestration
```

**Design Decision**: All implementation is in a private `_sdk` module. Users interact only via CLI with no public Python API.

---

## Implementation Phases

### Phase 1: Schema Converter
**Outcome**: Utility that converts JSON Schema to Python TypedDict definitions

**Handles**:

| JSON Schema | Python Type | Notes |
|-------------|-------------|-------|
| `{"type": "string"}` | `str` | |
| `{"type": "integer"}` | `int` | |
| `{"type": "number"}` | `float` | |
| `{"type": "boolean"}` | `bool` | |
| `{"type": "null"}` | `None` | |
| `{"type": "array", "items": {...}}` | `list[T]` | Recursive item type |
| `{"type": "object", "additionalProperties": true}` | `dict[str, Any]` | Generic dict |
| `{"type": "object", "additionalProperties": {"type": "string"}}` | `dict[str, str]` | Typed dict values |
| `{"type": "object", "properties": {...}}` | Nested TypedDict | Generate inline or named |
| `{"anyOf": [{"type": "T"}, {"type": "null"}]}` | `T \| None` | Nullable pattern |
| `{"anyOf": [{"type": "string"}, {"type": "integer"}]}` | `str \| int` | Union types |
| `{"anyOf": [...3+ types...]}` | `T1 \| T2 \| T3` | Multi-type union |
| `{"enum": ["A", "B", "C"], "type": "string"}` | `Literal["A", "B", "C"]` | String enums |
| `{"enum": [1, 2, 3], "type": "integer"}` | `Literal[1, 2, 3]` | Integer enums |
| `{"$ref": "#/definitions/Foo"}` | Resolved type | See reference resolution |
| `{"prefixItems": [...], "type": "array"}` | `tuple[T1, T2, ...]` | Fixed-length tuples |
| No `type` key present | `Any` | Non-Pydantic user classes |
| `{}` (empty schema) | `Any` | Permissive fallback |

**Reference Resolution** (`$ref` and `definitions`):
- Schemas may contain `"definitions": {"Foo": {...}}` with `"$ref": "#/definitions/Foo"` pointers
- Pydantic v2 may also use `"$defs"` instead of `"definitions"` - support both
- References must be resolved before type conversion
- Circular references → detect and emit `Any` with warning

**Required vs Optional Logic**:
- Field is **required** (no `NotRequired`) if:
  - Listed in schema's `"required"` array AND
  - Does NOT have a `"default"` key in its property definition
- Field is **optional** (`NotRequired[T]`) if:
  - NOT listed in `"required"` array, OR
  - HAS a `"default"` key (regardless of `required` list)

This matches how Prefect's server validates parameters (`actions.py:287-304`).

**Status**:
- [ ] Schema converter module created
- [ ] Primitive type conversion
- [ ] Array/list conversion with item types
- [ ] Object/dict conversion (additionalProperties variants)
- [ ] Nullable (anyOf with null) conversion
- [ ] Multi-type union conversion
- [ ] Enum → Literal conversion
- [ ] Reference resolution (definitions and $defs)
- [ ] Tuple (prefixItems) conversion
- [ ] Required vs optional with default handling
- [ ] Circular reference detection
- [ ] Unit tests pass
- [ ] Type checker (pyright) passes

---

### Phase 2: Naming & Data Models
**Outcome**: Utilities for converting arbitrary names to valid Python identifiers, plus internal data models

**Naming Conversion**:

| Input | Identifier | Class Name |
|-------|------------|------------|
| `my-flow` | `my_flow` | `MyFlow` |
| `123-start` | `_123_start` | `_123Start` |
| `class` | `class_` | `Class_` |
| `my_flow` | `my_flow` | `MyFlow` |
| `café-data` | `caf_data` | `CafData` |
| `🚀-deploy` | `_deploy` | `Deploy` |

**Conversion Rules**:
1. Strip/replace non-ASCII characters with underscores
2. Replace hyphens and spaces with underscores
3. Collapse consecutive underscores
4. Prefix with underscore if starts with digit
5. Append underscore if Python keyword (`class` → `class_`)
6. Handle empty result after stripping → `_unnamed`

**Reserved Names** (must be avoided via suffix):

| Context | Reserved Names |
|---------|----------------|
| Flow identifiers | `flows` (conflicts with root namespace) |
| Deployment identifiers | `run`, `run_async` (conflicts with methods) |
| TypedDict class names | Generated class names in same file |

**Collision Resolution**:
- When two names normalize to the same identifier: append `_2`, `_3`, etc.
- Example: `my-flow` and `my_flow` both become `my_flow` → second becomes `my_flow_2`
- Preserve original name in docstring for discoverability

**Data Models**:
- `WorkPoolInfo` - Work pool name, type, variables schema (JSON Schema dict)
- `DeploymentInfo` - Deployment name, flow name, parameter schema, work pool reference
- `FlowInfo` - Flow name with list of deployments
- `SDKData` - Complete data needed for generation (flows, work pools, metadata)

**Status**:
- [ ] Naming utilities created
- [ ] Safe identifier conversion (ASCII, keywords, digits)
- [ ] Safe class name conversion (PascalCase)
- [ ] Reserved name detection and avoidance
- [ ] Collision detection and suffix generation
- [ ] Data models created
- [ ] Unit tests for edge cases (emoji, all-unicode, empty, keywords)
- [ ] Unit tests pass

---

### Phase 3: Template & Renderer
**Outcome**: Jinja2 template that produces valid, type-safe Python code

This is the core of the feature—it defines exactly what users receive when they run the generator.

#### Generated File Structure

The output file has 5 distinct sections, generated in this order:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. MODULE HEADER                                            │
│    - Docstring with generation metadata                     │
│    - Imports (typing, TypedDict, NotRequired, overload)     │
│    - TYPE_CHECKING block for FlowRun import                 │
├─────────────────────────────────────────────────────────────┤
│ 2. DEPLOYMENT NAME LITERAL                                  │
│    - DeploymentName = Literal["flow/deploy", ...]           │
│    - Enables autocomplete for all deployment names          │
├─────────────────────────────────────────────────────────────┤
│ 3. WORK POOL TYPEDDICTS                                     │
│    - {WorkPoolName}JobVariables TypedDict                   │
├─────────────────────────────────────────────────────────────┤
│ 4. DEPLOYMENT CLASSES                                       │
│    - One class per deployment                               │
│    - with_options() for infrastructure config (returns self)│
│    - run()/run_async() with flow params as direct kwargs    │
├─────────────────────────────────────────────────────────────┤
│ 5. DEPLOYMENT NAMESPACE                                     │
│    - Single `deployments` class with from_name() method     │
│    - @overload per deployment for type-safe return types    │
│    - This is the public entry point                         │
└─────────────────────────────────────────────────────────────┘
```

#### Section 1: Module Header

Generated metadata helps users understand the SDK's origin and freshness:

```python
"""
Prefect SDK - Auto-generated typed client for workspace deployments.

Generated at: 2026-01-06T14:30:00Z
Prefect version: 3.2.0
Workspace: my-workspace (if available)

This file was auto-generated by `prefect sdk generate`.
Do not edit manually - regenerate after deployment changes.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Any, Iterable, Literal, overload

from typing_extensions import NotRequired, TypedDict

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
```

**Python 3.10+ Compatibility**:
- `NotRequired` is imported from `typing_extensions` (not `typing`) for Python 3.10 support
- `TypedDict` from `typing_extensions` has better feature support than `typing.TypedDict`
- `Literal` from `typing` (available since 3.8) for deployment name types
- `overload` from `typing` for type-safe `from_name()` dispatch

**Import design**:
- Minimal imports to reduce load time
- `FlowRun` under `TYPE_CHECKING` avoids circular imports and heavy import chains
- Generated SDK only depends on `typing_extensions` and `prefect` (already a dependency)

#### Section 2: DeploymentName Literal

A `Literal` type containing all deployment names enables IDE autocomplete:

```python
DeploymentName = Literal[
    "my-etl-flow/production",
    "my-etl-flow/staging",
    "data-sync/daily",
]
```

**Design decisions**:
- Uses the full `flow-name/deployment-name` format (matches `run_deployment()`)
- Deployment names with special characters are escaped appropriately
- Empty workspaces: `DeploymentName = Literal[""]` (placeholder, will fail at runtime)

#### Section 3: Work Pool TypedDicts

Each work pool gets a TypedDict for its job variables:

```python
class KubernetesPoolJobVariables(TypedDict, total=False):
    """Job variables for work pool: kubernetes-pool"""
    image: NotRequired[str]
    namespace: NotRequired[str]
    cpu_request: NotRequired[str]
    memory_request: NotRequired[str]
```

**Design decisions**:
- `total=False` with explicit `NotRequired` gives clearest IDE hints
- Class name format: `{WorkPoolName}JobVariables` (PascalCase)
- Empty work pools or empty job variables schema: no TypedDict generated
- Docstring identifies the source work pool

#### Section 4: Deployment Classes

Each deployment gets a class with `with_options()`, `run()`, and `run_async()` methods:

```python
class _MyEtlFlowProduction:
    """
    Deployment: my-etl-flow/production
    Work Pool: kubernetes-pool
    """

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}

    def _copy_with_options(self, options: dict[str, Any]) -> "_MyEtlFlowProduction":
        """Create a new instance with the given options dict."""
        new = _MyEtlFlowProduction()
        new._options = options
        return new

    def with_options(
        self,
        *,
        timeout: float | None = None,
        poll_interval: float | None = None,
        tags: Iterable[str] | None = None,
        idempotency_key: str | None = None,
        work_queue_name: str | None = None,
        as_subflow: bool | None = None,
        scheduled_time: datetime | None = None,
        flow_run_name: str | None = None,
        job_variables: KubernetesPoolJobVariables | None = None,  # Typed per work pool
    ) -> "_MyEtlFlowProduction":
        """Create a new deployment handle with updated options.

        Returns a new instance with merged options (does not mutate self).
        This matches the behavior of Flow.with_options() and Task.with_options().
        """
        new_options = self._options.copy()
        if timeout is not None:
            new_options["timeout"] = timeout
        if poll_interval is not None:
            new_options["poll_interval"] = poll_interval
        if tags is not None:
            new_options["tags"] = tags
        if idempotency_key is not None:
            new_options["idempotency_key"] = idempotency_key
        if work_queue_name is not None:
            new_options["work_queue_name"] = work_queue_name
        if as_subflow is not None:
            new_options["as_subflow"] = as_subflow
        if scheduled_time is not None:
            new_options["scheduled_time"] = scheduled_time
        if flow_run_name is not None:
            new_options["flow_run_name"] = flow_run_name
        if job_variables is not None:
            new_options["job_variables"] = job_variables
        return self._copy_with_options(new_options)

    def run(
        self,
        source: str,               # Required flow param
        batch_size: int = 100,     # Optional flow param with default
        full_refresh: bool = False,
    ) -> "FlowRun":
        """Run the my-etl-flow/production deployment synchronously."""
        from prefect.deployments import run_deployment

        parameters: dict[str, Any] = {"source": source}
        if batch_size != 100:
            parameters["batch_size"] = batch_size
        if full_refresh != False:
            parameters["full_refresh"] = full_refresh

        return run_deployment(
            name="my-etl-flow/production",
            parameters=parameters,
            **self._options,
        )

    async def run_async(
        self,
        source: str,
        batch_size: int = 100,
        full_refresh: bool = False,
    ) -> "FlowRun":
        """Run the my-etl-flow/production deployment asynchronously."""
        from prefect.deployments import run_deployment

        parameters: dict[str, Any] = {"source": source}
        if batch_size != 100:
            parameters["batch_size"] = batch_size
        if full_refresh != False:
            parameters["full_refresh"] = full_refresh

        return await run_deployment(
            name="my-etl-flow/production",
            parameters=parameters,
            **self._options,
        )
```

**Design decisions**:
- Class name format: `_{FlowName}{DeploymentName}` (underscore prefix = private)
- **`with_options()` returns a new instance** - matches `Flow.with_options()` / `Task.with_options()` behavior
- **Flow parameters are direct kwargs on `run()`/`run_async()`** - enables IDE autocomplete and type checking
- **`job_variables` typed per work pool** - uses `{WorkPoolName}JobVariables` TypedDict
- All `with_options()` params are keyword-only (after `*`) and optional
- Required flow params have no default; optional params have defaults from schema
- Import uses public API path: `from prefect.deployments import run_deployment`
- Import inside method body avoids import-time side effects
- Docstring includes full deployment name and work pool for discoverability
- `run()` calls `run_deployment()` synchronously (the decorator handles sync execution)
- `run_async()` uses `await run_deployment()` for proper async execution

**Flow parameter handling**:
- Required params (in schema's `required` array, no default) → required kwargs
- Optional params (not in `required` or has `default`) → kwargs with defaults
- Default values come from schema's `default` field when present
- Parameters collected into dict before passing to `run_deployment()`

**Edge cases**:
- If deployment has no work pool → `with_options()` has no `job_variables` param
- If flow has no parameters → `run()`/`run_async()` have no params

#### Section 5: Deployment Namespace

The single public entry point with type-safe `from_name()` method:

```python
class deployments:
    """
    Access deployments by name.

    Usage:
        from my_sdk import deployments

        flow_run = deployments.from_name("my-etl-flow/production").with_options(
            timeout=60,
            job_variables={"memory": "8Gi"},
        ).run(
            source="s3://bucket",
            batch_size=100,
        )

    Available deployments:
        - my-etl-flow/production
        - my-etl-flow/staging
        - data-sync/daily
    """

    @overload
    @staticmethod
    def from_name(name: Literal["my-etl-flow/production"]) -> _MyEtlFlowProduction: ...

    @overload
    @staticmethod
    def from_name(name: Literal["my-etl-flow/staging"]) -> _MyEtlFlowStaging: ...

    @overload
    @staticmethod
    def from_name(name: Literal["data-sync/daily"]) -> _DataSyncDaily: ...

    @staticmethod
    def from_name(name: DeploymentName) -> _MyEtlFlowProduction | _MyEtlFlowStaging | _DataSyncDaily:
        """Get a deployment by name.

        Args:
            name: The deployment name in "flow-name/deployment-name" format.

        Returns:
            A deployment object with run() and run_async() methods.

        Raises:
            KeyError: If the deployment name is not found.
        """
        _deployments: dict[str, Any] = {
            "my-etl-flow/production": _MyEtlFlowProduction(),
            "my-etl-flow/staging": _MyEtlFlowStaging(),
            "data-sync/daily": _DataSyncDaily(),
        }
        return _deployments[name]


__all__ = ["deployments", "DeploymentName"]
```

**Design decisions**:
- Lowercase `deployments` (not `Deployments`) for natural usage
- `from_name()` is a `@staticmethod` - no instance needed
- `@overload` for each deployment enables type-safe return types
- Each overload uses `Literal["exact-name"]` for precise typing
- Implementation function has union return type for runtime
- Export both `deployments` and `DeploymentName` for user convenience
- Docstring lists all available deployments for discoverability

#### Renderer Module

The renderer takes `SDKData` and produces the output file:

```
render_sdk(data: SDKData, output_path: Path) -> None
```

**Responsibilities**:
1. Load Jinja2 template from package resources
2. Convert data models to template-friendly dicts (with schema → TypedDict conversion)
3. Render template with context
4. Write output file (creating parent directories if needed)

**Template context includes**:
- `generation_time` - ISO timestamp
- `prefect_version` - Current Prefect version
- `workspace_name` - Workspace name if available
- `module_name` - Output file stem (for docstring examples)
- `work_pools` - Dict of work pool data with converted TypedDict fields
- `deployments` - List of deployment data with parameter schemas

#### Edge Cases to Handle

**Schema Edge Cases**:

| Scenario | Behavior |
|----------|----------|
| `parameter_openapi_schema` is `None` | No flow param kwargs, only `*, options` |
| `parameter_openapi_schema` is `{}` | No flow param kwargs, only `*, options` |
| `parameter_openapi_schema` is `{"type": "object", "properties": {}}` | No flow param kwargs, only `*, options` |
| `base_job_template["variables"]` missing | Use base `RunOptions`, no `job_variables` field |
| `base_job_template["variables"]["properties"]` is `{}` | Generate `{WorkPoolName}RunOptions` without `job_variables` |
| Schema has circular `$ref` | Emit `Any` type with generation warning |
| Schema uses `$defs` instead of `definitions` | Support both (Pydantic v2 compatibility) |
| Property has no `type` key | Emit `Any` type |
| `definitions` key missing from schema | Use empty dict as fallback |

**Naming Edge Cases**:

| Scenario | Behavior |
|----------|----------|
| Deployment class name conflicts | Append numeric suffix (`_MyEtlFlowProduction2`) |
| Deployment name contains quotes | Escape in Literal type string |
| Very long deployment names | Class name truncated, full name in Literal |
| Name is entirely non-ASCII | Use `_unnamed` with suffix if needed |
| Name is empty string | Use `_unnamed` with suffix if needed |
| Name is Python keyword | Append underscore (`class` → `class_`) |

**Structural Edge Cases**:

| Scenario | Behavior |
|----------|----------|
| Deployment with no work pool | `with_options()` has no `job_variables` param |
| No deployments match filter | Error with helpful message |
| Zero deployments in workspace | Error with helpful message |
| Deployments of same flow have different schemas | Use first deployment's schema, log warning |

**General rules**:
- If a work pool has empty job variables schema → `with_options()` has no `job_variables` param
- If deployment has no work pool → `with_options()` has no `job_variables` param
- If flow has no parameters → `run()`/`run_async()` have no params
- Each deployment gets one `@overload` in the `deployments` class

#### Status

**Template**:
- [ ] Module header section
- [ ] DeploymentName Literal section
- [ ] Work pool TypedDict section
- [ ] Deployment class section (with with_options/run/run_async)
- [ ] Deployments namespace section
- [ ] Edge case handling (empty schemas, missing work pools, name conflicts)

**Renderer**:
- [ ] Template loading from package resources
- [ ] Data model → template context conversion
- [ ] Schema → TypedDict field conversion integration
- [ ] File writing with directory creation

**Verification**:
- [ ] Generated code is valid Python (parseable by `ast.parse`)
- [ ] Generated code passes `pyright --strict`
- [ ] IDE autocomplete works for `deployments.from_name().with_options().run()`
- [ ] IDE shows parameter hints with correct types
- [ ] Generated docstrings render correctly in IDE

---

### Phase 4: Data Fetching & Generator
**Outcome**: API integration and orchestration layer

**Prerequisites**:
- User must be authenticated (either to Prefect Cloud or a local/remote server)
- Check authentication before fetching and provide clear error message if not configured

**Fetcher Responsibilities**:
- Check authentication status before making API calls
- Query deployments from Prefect API (limited to current workspace/server)
- Fetch work pool schemas for referenced work pools (batch/parallel where possible)
- Group deployments by flow
- Handle missing/deleted work pools gracefully (omit job_variables typing)

**Generator Responsibilities**:
- Orchestrate fetch → render → write pipeline
- Apply flow/deployment filters
- Report generation statistics (flow count, deployment count, work pool count)
- Error clearly when no deployments match filters

**Error Handling Strategy**:

| Error | Behavior |
|-------|----------|
| Not authenticated | Error: "Not authenticated. Run `prefect cloud login` or configure PREFECT_API_URL." |
| API unreachable | Error: "Could not connect to Prefect API at {url}. Check your configuration." |
| No deployments found | Error: "No deployments found in workspace." |
| No deployments match filter | Error: "No deployments matched filters. Found N deployments total." |
| Work pool fetch fails | Warning, continue without job_variables typing for affected deployments |
| Invalid schema in deployment | Warning, use `Any` type for affected parameters |
| Single deployment fetch fails | Warning, skip deployment, continue with others |

**Partial Failure Policy**: The generator should be resilient. Individual deployment or work pool failures should log warnings but not abort the entire generation. Only fail if:
- Authentication fails
- API is completely unreachable
- Zero deployments can be processed

**Status**:
- [ ] Authentication check implemented
- [ ] Fetcher module created
- [ ] Deployment listing with pagination
- [ ] Work pool fetching (parallel/batched)
- [ ] Graceful handling of missing work pools
- [ ] Generator orchestrator created
- [ ] Flow/deployment filtering
- [ ] Partial failure handling with warnings
- [ ] Works against live Prefect API
- [ ] Generated SDK works end-to-end
- [ ] **Checkpoint**: Manually verified with real data before proceeding to CLI

---

### Phase 5: CLI Command
**Outcome**: Public `prefect sdk generate` command

**User Feedback**:
- Progress spinner while fetching
- Warnings for any skipped deployments or work pools
- Summary of generated content (flows, deployments, work pools)
- Usage hint showing how to import the SDK
- Clear error messages for failures

**File Handling**:
- Overwrites existing file without prompting (enables easy regeneration workflow)
- Creates parent directories if they don't exist

**Example Output (Success)**:
```
Fetching deployments...
⚠ Warning: Could not fetch work pool 'old-pool' - job_variables will be untyped for affected deployments

SDK generated successfully!

  Flows:       3
  Deployments: 12
  Work pools:  2

  Output:      /path/to/my_sdk.py

Usage:
  from my_sdk import deployments
```

**Example Output (No Deployments)**:
```
Error: No deployments found in workspace.

Make sure you have deployed at least one flow:
  prefect deploy
```

**Status**:
- [ ] CLI module created
- [ ] CLI registered in prefect.cli
- [ ] `prefect sdk generate --help` shows documentation
- [ ] Progress indicator visible during generation
- [ ] Warnings displayed for partial failures
- [ ] Clear error message if not authenticated
- [ ] Clear error message if no deployments found
- [ ] Overwrites existing files
- [ ] Creates parent directories
- [ ] CLI tests pass

---

## Verification Checklist

### Automated
- [ ] All unit tests pass (`uv run pytest tests/_sdk/`)
- [ ] CLI tests pass (`uv run pytest tests/cli/test_sdk.py`)
- [ ] Type checker passes (`uv run pyright src/prefect/_sdk/ src/prefect/cli/sdk.py`)
- [ ] Linter passes (`uv run ruff check src/prefect/_sdk/ src/prefect/cli/sdk.py`)
- [ ] Generated SDK passes `pyright --strict`
- [ ] Generated SDK is valid Python (`ast.parse()` succeeds)

### Manual
- [ ] Generate SDK against Prefect Cloud workspace
- [ ] Verify IDE autocomplete in VS Code/PyCharm
- [ ] Confirm type errors are caught for invalid parameters
- [ ] Successfully run a deployment using generated SDK (sync)
- [ ] Successfully run a deployment using generated SDK (async)
- [ ] Test with deployment that has no work pool
- [ ] Test with flow that has no parameters
- [ ] Test with enum parameters (verify Literal types work)
- [ ] Test filtering with `--flow` and `--deployment` flags
- [ ] Verify regeneration overwrites existing file correctly

---

## Scope Boundaries

**In Scope**:
- Single Python file output
- TypedDict for type hints
- Sync and async run methods
- Work pool job variable typing
- Flow parameter typing

**Out of Scope**:
- Real-time SDK updates (webhook-based regeneration)
- Non-Python SDK generation
- Pydantic model generation
- Multi-file module output
- Diffing/merge support for regeneration

---

## Performance Expectations

- Handles up to 500 deployments (captures 99.9% of use cases)
- API calls are parallelized where possible (use `asyncio.gather` for work pool fetches)
- Generated file size: ~10-20KB for 500 deployments
- Generation time: Dominated by API calls, template rendering is fast

---

## Template Safety

**String Escaping in Generated Code**:

The Jinja2 template must handle user-controlled strings (deployment names, flow names, descriptions) safely:

| Context | Handling |
|---------|----------|
| Docstrings | Escape or strip triple quotes (`"""` → `'''` or filtered) |
| String literals | Escape quotes, backslashes |
| Identifiers | Already sanitized by naming utilities |

**Example Problem**:
```python
# If flow description contains: """Hello"""
class _MyFlow:
    """
    Flow: my-flow
    Description: """Hello"""  # SYNTAX ERROR!
    """
```

**Solution**: Strip or escape problematic characters in user-provided text before template rendering. The naming utilities handle identifiers; a separate text sanitizer handles docstring content.

---

## Versioning Considerations

**Compatibility**:
- Generated SDK calls `run_deployment()` which is a stable public API
- Parameter signature changes in future Prefect versions may require SDK regeneration
- Generated docstring includes Prefect version for reference

**Recommendation**: Regenerate SDK when:
- Deployments are added/removed/renamed
- Work pool schemas change
- Prefect is upgraded to a new major/minor version
