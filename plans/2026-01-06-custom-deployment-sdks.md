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
from my_sdk import flows

# IDE autocomplete, type checking, errors caught immediately
flows.my_etl_flow.production.run(
    parameters={"source": "s3://bucket"},  # Typo would be caught by type checker
    job_variables={"memory": "8Gi"},  # Typed based on work pool schema
)
```

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
1. **TypedDict for each work pool** - Typed job variables from `WorkPool.base_job_template["variables"]`
2. **TypedDict for each flow** - Typed parameters from `Deployment.parameter_openapi_schema`
3. **Class for each deployment** - With `run()` and `run_async()` methods
4. **Namespace hierarchy** - `flows.<flow_name>.<deployment_name>.run()`

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

The output file has 6 distinct sections, generated in this order:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. MODULE HEADER                                            │
│    - Docstring with generation metadata                     │
│    - Imports (typing, TypedDict, NotRequired, etc.)         │
│    - TYPE_CHECKING block for FlowRun import                 │
├─────────────────────────────────────────────────────────────┤
│ 2. WORK POOL TYPEDDICTS                                     │
│    - One TypedDict per work pool                            │
│    - Fields from work pool's base_job_template.variables    │
├─────────────────────────────────────────────────────────────┤
│ 3. FLOW PARAMETER TYPEDDICTS                                │
│    - One TypedDict per flow (not per deployment)            │
│    - Fields from flow's parameter_openapi_schema            │
├─────────────────────────────────────────────────────────────┤
│ 4. DEPLOYMENT CLASSES                                       │
│    - One class per deployment                               │
│    - Contains run() and run_async() static methods          │
├─────────────────────────────────────────────────────────────┤
│ 5. FLOW CLASSES                                             │
│    - One class per flow                                     │
│    - Aggregates deployment instances as class attributes    │
├─────────────────────────────────────────────────────────────┤
│ 6. ROOT NAMESPACE                                           │
│    - Single `flows` class                                   │
│    - Aggregates flow instances as class attributes          │
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
from typing import TYPE_CHECKING, Any, Iterable, Literal

from typing_extensions import NotRequired, TypedDict

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
```

**Python 3.10+ Compatibility**:
- `NotRequired` is imported from `typing_extensions` (not `typing`) for Python 3.10 support
- `TypedDict` from `typing_extensions` has better feature support than `typing.TypedDict`
- `Literal` from `typing` (available since 3.8) for enum types

**Import design**:
- Minimal imports to reduce load time
- `FlowRun` under `TYPE_CHECKING` avoids circular imports and heavy import chains
- Generated SDK only depends on `typing_extensions` and `prefect` (already a dependency)

#### Section 2: Work Pool TypedDicts

Each work pool gets a TypedDict representing its job variables schema:

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
- Empty work pools generate `pass` body
- Docstring identifies the source work pool

#### Section 3: Flow Parameter TypedDicts

Each flow gets one TypedDict for its parameters, generated from the **server-side OpenAPI schema** (`deployment.parameter_openapi_schema`):

```python
class MyEtlFlowParams(TypedDict, total=False):
    """Parameters for flow: my-etl-flow"""
    source: str                      # Required fields have no NotRequired
    batch_size: NotRequired[int]     # Optional fields use NotRequired
    full_refresh: NotRequired[bool]
```

**Data source**: The parameter schema is fetched from the Prefect API via `DeploymentResponse.parameter_openapi_schema`. This is a JSON Schema that was captured when the deployment was created. **The generator has no access to flow source code**—it works entirely from server-side metadata.

**Empty Schema Detection**: A schema is considered "empty" (no TypedDict generated) if any of:
- `parameter_openapi_schema` is `None`
- `parameter_openapi_schema` is `{}`
- `parameter_openapi_schema.get("properties", {})` is empty

**Design decisions**:
- One TypedDict per flow, not per deployment (parameter schema is typically identical across a flow's deployments)
- Required fields listed first, then optional (alphabetically within each group)
- Class name format: `{FlowName}Params` (PascalCase)
- If deployments of the same flow have different schemas (edge case), use the first deployment's schema and log a warning

#### Section 4: Deployment Classes

Each deployment gets a class with `run()` and `run_async()` methods:

```python
class _MyEtlFlowProduction:
    """
    Deployment: my-etl-flow/production
    Work Pool: kubernetes-pool
    """

    @staticmethod
    def run(
        parameters: MyEtlFlowParams | None = None,
        scheduled_time: datetime | None = None,
        flow_run_name: str | None = None,
        timeout: float | None = None,
        poll_interval: float | None = 5,
        tags: Iterable[str] | None = None,
        idempotency_key: str | None = None,
        work_queue_name: str | None = None,
        as_subflow: bool | None = True,
        job_variables: KubernetesPoolJobVariables | None = None,
    ) -> "FlowRun":
        """Run the my-etl-flow/production deployment synchronously."""
        from prefect.deployments import run_deployment
        return run_deployment(
            name="my-etl-flow/production",
            parameters=parameters,
            scheduled_time=scheduled_time,
            flow_run_name=flow_run_name,
            timeout=timeout,
            poll_interval=poll_interval,
            tags=tags,
            idempotency_key=idempotency_key,
            work_queue_name=work_queue_name,
            as_subflow=as_subflow,
            job_variables=job_variables,
        )

    @staticmethod
    async def run_async(
        parameters: MyEtlFlowParams | None = None,
        scheduled_time: datetime | None = None,
        flow_run_name: str | None = None,
        timeout: float | None = None,
        poll_interval: float | None = 5,
        tags: Iterable[str] | None = None,
        idempotency_key: str | None = None,
        work_queue_name: str | None = None,
        as_subflow: bool | None = True,
        job_variables: KubernetesPoolJobVariables | None = None,
    ) -> "FlowRun":
        """Run the my-etl-flow/production deployment asynchronously."""
        from prefect.deployments import run_deployment
        return await run_deployment(
            name="my-etl-flow/production",
            parameters=parameters,
            scheduled_time=scheduled_time,
            flow_run_name=flow_run_name,
            timeout=timeout,
            poll_interval=poll_interval,
            tags=tags,
            idempotency_key=idempotency_key,
            work_queue_name=work_queue_name,
            as_subflow=as_subflow,
            job_variables=job_variables,
        )
```

**Design decisions**:
- Class name format: `_{FlowName}{DeploymentName}` (underscore prefix = private)
- `@staticmethod` allows calling without instantiation while keeping namespace
- `parameters` typed to flow's TypedDict
- `job_variables` typed to work pool's TypedDict
- Parameter order matches `run_deployment()` (minus `client` which is auto-injected)
- **`client` parameter is NOT exposed** - it's injected by `@inject_client` decorator at runtime
- Import uses public API path: `from prefect.deployments import run_deployment`
- Import inside method body avoids import-time side effects
- Docstring includes full deployment name and work pool for discoverability
- `run()` calls `run_deployment()` synchronously (the decorator handles sync execution)
- `run_async()` uses `await run_deployment()` for proper async execution

**Edge cases**:
- If deployment has no work pool → omit `job_variables` parameter entirely
- If work pool has empty variables schema → omit `job_variables` parameter entirely
- If flow has no parameters schema → omit `parameters` parameter entirely

#### Section 5: Flow Classes

Each flow aggregates its deployments:

```python
class _MyEtlFlow:
    """
    Flow: my-etl-flow

    Deployments:
        - production
        - staging
    """
    production = _MyEtlFlowProduction()
    staging = _MyEtlFlowStaging()
```

**Design decisions**:
- Class name format: `_{FlowName}` (underscore prefix = private)
- Deployment attribute names are snake_case identifiers
- Docstring lists all available deployments for discoverability

#### Section 6: Root Namespace

The single public entry point:

```python
class flows:
    """
    Access all flows and their deployments.

    Usage:
        from my_sdk import flows

        flow_run = flows.my_etl_flow.production.run(
            parameters={"source": "s3://bucket"},
        )

    Available flows:
        - my_etl_flow
        - data_sync
    """
    my_etl_flow = _MyEtlFlow()
    data_sync = _DataSync()

__all__ = ["flows"]
```

**Design decisions**:
- Lowercase `flows` (not `Flows`) for natural usage: `flows.my_flow`
- Only export `flows` in `__all__` - TypedDicts are available but not promoted
- Docstring includes usage example and lists all flows

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
- `flows` - List of flow data with nested deployments

#### Edge Cases to Handle

**Schema Edge Cases**:

| Scenario | Behavior |
|----------|----------|
| `parameter_openapi_schema` is `None` | Omit `parameters` kwarg |
| `parameter_openapi_schema` is `{}` | Omit `parameters` kwarg |
| `parameter_openapi_schema` is `{"type": "object", "properties": {}}` | Omit `parameters` kwarg |
| `base_job_template["variables"]` missing | Omit `job_variables` kwarg |
| `base_job_template["variables"]["properties"]` is `{}` | Omit `job_variables` kwarg |
| Schema has circular `$ref` | Emit `Any` type with generation warning |
| Schema uses `$defs` instead of `definitions` | Support both (Pydantic v2 compatibility) |
| Property has no `type` key | Emit `Any` type |
| `definitions` key missing from schema | Use empty dict as fallback |

**Naming Edge Cases**:

| Scenario | Behavior |
|----------|----------|
| Name conflicts after normalization | Append numeric suffix (`my_flow_2`) |
| Flow name = `flows` | Append suffix → `flows_2` |
| Deployment name = `run` or `run_async` | Append suffix → `run_2` |
| Very long names (>64 chars after conversion) | Truncate and ensure uniqueness |
| Name is entirely non-ASCII | Use `_unnamed` with suffix if needed |
| Name is empty string | Use `_unnamed` with suffix if needed |
| Name is Python keyword | Append underscore (`class` → `class_`) |

**Structural Edge Cases**:

| Scenario | Behavior |
|----------|----------|
| Flow with no deployments | Skip (don't generate empty flow class) |
| Deployment with no work pool | Omit `job_variables` kwarg |
| No deployments match filter | Error with helpful message |
| Zero deployments in workspace | Error with helpful message |
| Same deployment name under different flows | OK - namespaced by flow class |
| Deployments of same flow have different schemas | Use first deployment's schema, log warning |

**General rule**: If a TypedDict would have zero fields, don't generate it and omit the corresponding kwarg from the method signature.

#### Status

**Template**:
- [ ] Module header section
- [ ] Work pool TypedDict section
- [ ] Flow parameter TypedDict section
- [ ] Deployment class section (with run/run_async)
- [ ] Flow class section
- [ ] Root namespace section
- [ ] Edge case handling (empty schemas, missing work pools, name conflicts)

**Renderer**:
- [ ] Template loading from package resources
- [ ] Data model → template context conversion
- [ ] Schema → TypedDict field conversion integration
- [ ] File writing with directory creation

**Verification**:
- [ ] Generated code is valid Python (parseable by `ast.parse`)
- [ ] Generated code passes `pyright --strict`
- [ ] IDE autocomplete works for `flows.X.Y.run()`
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
  from my_sdk import flows
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
