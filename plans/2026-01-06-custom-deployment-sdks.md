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
    timeout=60,                              # Run options via method
).with_infra(
    memory="8Gi",                            # Job variables typed per work pool
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
2. **Per-work-pool TypedDicts** - `{WorkPoolName}JobVariables` for typed `with_infra()` kwargs
3. **Class for each deployment** - With `with_options()`, `with_infra()`, `run()`, and `run_async()` methods
4. **`deployments` namespace** - With `from_name()` method using `@overload` for type-safe dispatch

**Usage**: `deployments.from_name("flow/deploy").with_options(timeout=60).with_infra(memory="8Gi").run(param=val)`

**Important**: All type information comes from **server-side metadata** (JSON Schema stored with deployments and work pools). The generator does not inspect flow source code—it works entirely from the Prefect API.

## Key Design Decision: kwargs over TypedDict

We chose to use **direct kwargs** for flow parameters, run options, and job variables rather than TypedDict parameters:

```python
# ✅ Chosen approach: direct kwargs
deployments.from_name("my-flow/prod").with_options(
    timeout=60,
    tags=["production"],
).run(
    source="s3://bucket",
    batch_size=100,
)

# ❌ Rejected: TypedDict parameters
deployments.from_name("my-flow/prod").run(
    parameters={"source": "s3://bucket", "batch_size": 100},
    options={"timeout": 60, "tags": ["production"]},
)
```

**Rationale**:
- **More Pythonic** - Keyword arguments are the idiomatic Python way to pass named parameters
- **Better IDE experience** - Direct kwargs show parameter names and types in autocomplete; TypedDict requires remembering dict key names
- **Cleaner call sites** - No nested dict syntax, just natural function calls
- **Consistent with Prefect APIs** - Matches patterns like `@flow(retries=3)` and `task.with_options(timeout=60)`

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
- [x] Schema converter module created
- [x] Primitive type conversion
- [x] Array/list conversion with item types
- [x] Object/dict conversion (additionalProperties variants)
- [x] Nullable (anyOf with null) conversion
- [x] Multi-type union conversion
- [x] Enum → Literal conversion
- [x] Reference resolution (definitions and $defs)
- [x] Tuple (prefixItems) conversion
- [x] Required vs optional with default handling
- [x] Circular reference detection
- [x] Unit tests pass
- [x] Type checker (pyright) passes

**Phase 1 Implementation Notes** (deviations from plan):

1. **Objects with properties return `dict[str, Any]`, not nested TypedDict**
   - The plan's table shows `{"type": "object", "properties": {...}}` → `Nested TypedDict`
   - Implementation returns `dict[str, Any]` instead
   - Rationale: This converter produces type annotation *strings*. Generating nested TypedDict classes requires the template renderer (Phase 3) which can create named classes. The converter handles inline type annotations only.

2. **Circular reference handling is more nuanced**
   - The plan says: "Circular references → detect and emit `Any` with warning"
   - Implementation: Direct self-references raise `CircularReferenceError`. Indirect circular refs (objects with recursive properties) return `dict[str, Any]` because object conversion doesn't traverse properties. `extract_fields_from_schema()` catches `CircularReferenceError` and emits `Any` with warning.
   - Rationale: Different circular patterns require different handling; raising an exception for direct loops allows callers to decide how to handle it.

3. **Union flattening uses bracket/quote-aware splitting**
   - Not explicitly in plan, but necessary for correctness
   - Added `_split_union_top_level()` helper that respects `[]` brackets and `'"`quotes
   - Rationale: Naive splitting on ` | ` corrupts types like `list[str | int]` or `Literal['a | b']`

4. **Enum formatting uses `repr()` instead of manual escaping**
   - Plan doesn't specify escaping strategy
   - Implementation uses `repr()` for proper handling of control characters, unicode, and quotes
   - Rationale: `repr()` correctly handles all edge cases (newlines, tabs, backslashes, etc.)

5. **Float enum values are supported**
   - Plan only mentions string and integer enums
   - Implementation also supports float literals
   - Rationale: JSON Schema allows numeric enums; floats are valid Literal values in Python

6. **100% test coverage achieved**
   - 105 tests covering all code paths
   - Run with: `uv run pytest tests/_sdk/ --cov=src/prefect/_sdk --cov-report=term-missing`

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
- [x] Naming utilities created
- [x] Safe identifier conversion (ASCII, keywords, digits)
- [x] Safe class name conversion (PascalCase)
- [x] Reserved name detection and avoidance
- [x] Collision detection and suffix generation
- [x] Data models created
- [x] Unit tests for edge cases (emoji, all-unicode, empty, keywords)
- [x] Unit tests pass

**Phase 2 Implementation Notes** (deviations from plan):

1. **Unicode handling differs from plan**
   - Plan: "Strip/replace non-ASCII characters with underscores"
   - Implementation: Unicode separators/punctuation (em-dash, non-breaking space) become underscores; other non-ASCII chars are dropped after NFKD normalization
   - Rationale: Prevents word-merging (e.g., `a—b` → `a_b` not `ab`) while allowing accented chars to normalize (é → e)
   - Result: `café-data` → `cafe_data` (not `caf_data`), `🚀-deploy` → `deploy` (not `_deploy`)

2. **Class names don't get underscore suffix for keywords**
   - Plan: `class` → `Class_`
   - Implementation: `class` → `Class`
   - Rationale: Python is case-sensitive, so `Class` is valid. PascalCase naturally avoids keywords.

3. **Expanded reserved names beyond plan**
   - Plan: Flow=`{flows}`, Deployment=`{run, run_async}`
   - Implementation: Flow=`{flows, deployments, DeploymentName}`, Deployment=`{run, run_async, with_options, with_infra}`, Module=`{all}`
   - Rationale: Prevents conflicts with Phase 3 generated SDK surface

4. **Reserved names stored in normalized form**
   - Plan doesn't specify
   - Implementation: Reserved sets use normalized names (e.g., `"all"` not `"__all__"`) since `safe_identifier()` normalizes before checking
   - Rationale: Otherwise `safe_identifier("__all__", ..., "module")` would return `"all"` (not avoided)

5. **WorkPoolInfo.type renamed to pool_type**
   - Plan: `WorkPoolInfo` has `type` field
   - Implementation: Field named `pool_type`
   - Rationale: Avoids shadowing Python built-in `type`

6. **SDKData.deployment_names is derived, not stored**
   - Plan: `SDKData` has `deployment_names` as stored field
   - Implementation: Computed property derived from `flows`
   - Rationale: Single source of truth; prevents data divergence

7. **Deterministic ordering added**
   - Plan doesn't specify ordering
   - Implementation: `deployment_names` and `all_deployments()` return sorted results
   - Rationale: Ensures deterministic code generation regardless of API response order

8. **Additional SDKData convenience methods**
   - Plan doesn't specify
   - Implementation: Added `all_deployments()`, `flow_count`, `deployment_count`, `work_pool_count`
   - Rationale: Simplifies template rendering and statistics reporting

9. **SDKGenerationMetadata.api_url added**
   - Plan doesn't include this field
   - Implementation: Added `api_url` field
   - Rationale: Better traceability of SDK generation source

10. **German ß limitation**
    - Plan doesn't address
    - Implementation: ß is dropped (NFKD doesn't decompose it to "ss"), so `straße` → `strae`
    - Documented as known limitation

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
│    - with_options() for run config (tags, scheduling, etc.) │
│    - with_infra() for job variables (typed per work pool)   │
│    - run()/run_async() returns PrefectFlowRunFuture         │
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
    from prefect.futures import PrefectFlowRunFuture
```

**Python 3.10+ Compatibility**:
- `NotRequired` is imported from `typing_extensions` (not `typing`) for Python 3.10 support
- `TypedDict` from `typing_extensions` has better feature support than `typing.TypedDict`
- `Literal` from `typing` (available since 3.8) for deployment name types
- `overload` from `typing` for type-safe `from_name()` dispatch

**Import design**:
- Minimal imports to reduce load time
- `PrefectFlowRunFuture` under `TYPE_CHECKING` avoids circular imports and heavy import chains
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

Each deployment gets a class with `with_options()`, `with_infra()`, `run()`, and `run_async()` methods:

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
        tags: Iterable[str] | None = None,
        idempotency_key: str | None = None,
        work_queue_name: str | None = None,
        as_subflow: bool | None = None,
        scheduled_time: datetime | None = None,
        flow_run_name: str | None = None,
    ) -> "_MyEtlFlowProduction":
        """Create a new deployment handle with updated run options.

        Returns a new instance with merged options (does not mutate self).
        This matches the behavior of Flow.with_options() and Task.with_options().

        Note: timeout and poll_interval are not included here - use the
        PrefectFlowRunFuture.result(timeout=...) method for waiting.
        """
        new_options = self._options.copy()
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
        return self._copy_with_options(new_options)

    def with_infra(
        self,
        *,
        # Typed kwargs from work pool's job variables schema
        image: str | None = None,
        namespace: str | None = None,
        cpu_request: str | None = None,
        memory: str | None = None,
    ) -> "_MyEtlFlowProduction":
        """Create a new deployment handle with updated job variables.

        Returns a new instance with merged options (does not mutate self).
        Job variable types are derived from the work pool schema.
        """
        new_options = self._options.copy()
        job_variables = new_options.get("job_variables", {}).copy()
        if image is not None:
            job_variables["image"] = image
        if namespace is not None:
            job_variables["namespace"] = namespace
        if cpu_request is not None:
            job_variables["cpu_request"] = cpu_request
        if memory is not None:
            job_variables["memory"] = memory
        if job_variables:
            new_options["job_variables"] = job_variables
        return self._copy_with_options(new_options)

    def run(
        self,
        source: str,               # Required flow param
        batch_size: int = 100,     # Optional flow param with default
        full_refresh: bool = False,
    ) -> "PrefectFlowRunFuture":
        """Run the my-etl-flow/production deployment synchronously.

        Returns a PrefectFlowRunFuture that can be used to:
        - Get the flow_run_id immediately
        - Call .result() to wait for completion and get the result
        - Call .state to check current state
        """
        from prefect.deployments import run_deployment
        from prefect.futures import PrefectFlowRunFuture

        parameters: dict[str, Any] = {"source": source}
        if batch_size != 100:
            parameters["batch_size"] = batch_size
        if full_refresh != False:
            parameters["full_refresh"] = full_refresh

        flow_run = run_deployment(
            name="my-etl-flow/production",
            parameters=parameters,
            **self._options,
        )
        return PrefectFlowRunFuture(flow_run_id=flow_run.id)

    async def run_async(
        self,
        source: str,
        batch_size: int = 100,
        full_refresh: bool = False,
    ) -> "PrefectFlowRunFuture":
        """Run the my-etl-flow/production deployment asynchronously.

        Returns a PrefectFlowRunFuture that can be used to:
        - Get the flow_run_id immediately
        - Call .result() to wait for completion and get the result
        - Call .state to check current state
        """
        from prefect.deployments import run_deployment
        from prefect.futures import PrefectFlowRunFuture

        parameters: dict[str, Any] = {"source": source}
        if batch_size != 100:
            parameters["batch_size"] = batch_size
        if full_refresh != False:
            parameters["full_refresh"] = full_refresh

        flow_run = await run_deployment(
            name="my-etl-flow/production",
            parameters=parameters,
            **self._options,
        )
        return PrefectFlowRunFuture(flow_run_id=flow_run.id)
```

**Design decisions**:
- Class name format: `_{FlowName}{DeploymentName}` (underscore prefix = private)
- **`with_options()` for run config** - tags, scheduling, idempotency (timeout/polling handled by future)
- **`with_infra()` for job variables** - typed kwargs derived from work pool schema
- **Both methods return new instances** - matches `Flow.with_options()` / `Task.with_options()` behavior
- **Flow parameters are direct kwargs on `run()`/`run_async()`** - enables IDE autocomplete and type checking
- All `with_options()` and `with_infra()` params are keyword-only (after `*`) and optional
- Required flow params have no default; optional params have defaults from schema
- Import uses public API path: `from prefect.deployments import run_deployment`
- Import inside method body avoids import-time side effects
- Docstring includes full deployment name and work pool for discoverability
- `run()` and `run_async()` return `PrefectFlowRunFuture` for non-blocking access to flow run ID and eventual result

**Flow parameter handling**:
- Required params (in schema's `required` array, no default) → required kwargs
- Optional params (not in `required` or has `default`) → kwargs with defaults
- Default values come from schema's `default` field when present
- Parameters collected into dict before passing to `run_deployment()`

**Edge cases**:
- If deployment has no work pool → no `with_infra()` method generated
- If work pool has empty job variables schema → no `with_infra()` method generated
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
        ).with_infra(
            memory="8Gi",
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
| Deployment with no work pool | No `with_infra()` method generated |
| No deployments match filter | Error with helpful message |
| Zero deployments in workspace | Error with helpful message |
| Deployments of same flow have different schemas | Use first deployment's schema, log warning |

**General rules**:
- If a work pool has empty job variables schema → no `with_infra()` method generated
- If deployment has no work pool → no `with_infra()` method generated
- If flow has no parameters → `run()`/`run_async()` have no params
- Each deployment gets one `@overload` in the `deployments` class

#### Status

**Template**:
- [x] Module header section
- [x] DeploymentName Literal section
- [x] Work pool TypedDict section
- [x] Deployment class section (with with_options/run/run_async)
- [x] Deployments namespace section
- [x] Edge case handling (empty schemas, missing work pools, name conflicts)

**Renderer**:
- [x] Template loading from package resources
- [x] Data model → template context conversion
- [x] Schema → TypedDict field conversion integration
- [x] File writing with directory creation

**Verification**:
- [x] Generated code is valid Python (parseable by `ast.parse`)
- [x] Generated code passes pyright
- [ ] IDE autocomplete works for `deployments.from_name().with_options().with_infra().run()`
- [ ] IDE shows parameter hints with correct types
- [ ] Generated docstrings render correctly in IDE

**Phase 3 Implementation Notes** (deviations from plan):

1. **Single deployment doesn't use @overload**
   - Plan: Each deployment gets one `@overload` in the `deployments` class
   - Implementation: Single deployments don't use `@overload` (pyright requires 2+ overloads)
   - Rationale: Pyright emits error for single overload without implementation

2. **run() uses cast() for return type**
   - Plan: `run()` returns `FlowRun` directly from `run_deployment()`
   - Implementation: Uses `cast("FlowRun", run_deployment(...))`
   - Rationale: The `@async_dispatch` decorator on `run_deployment` makes pyright think it returns a union type

3. **Work pool TypedDicts use total=False without NotRequired**
   - Plan: Fields would use `NotRequired[T]` for optional fields
   - Implementation: Uses `total=False` on the TypedDict class (all fields optional)
   - Rationale: Job variables are always optional overrides; `total=False` is cleaner

4. **Tests: 270 tests total, 43 new renderer tests**
   - Run with: `uv run pytest tests/_sdk/ -v`

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
