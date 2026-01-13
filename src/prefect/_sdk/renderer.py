"""
SDK renderer module.

This module is responsible for converting SDKData into template-friendly
context and rendering the Jinja2 template to produce the final SDK file.
"""

import importlib.resources
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jinja2

from prefect._sdk.models import DeploymentInfo, SDKData, WorkPoolInfo
from prefect._sdk.naming import safe_class_name, safe_identifier
from prefect._sdk.schema_converter import extract_fields_from_schema
from prefect._sdk.types import FieldInfo


@dataclass
class ParameterContext:
    """Processed parameter information for template rendering."""

    name: str
    """Safe Python identifier for the parameter."""

    original_name: str
    """Original parameter name from schema."""

    python_type: str
    """Python type annotation string."""

    required: bool
    """Whether the parameter is required."""

    has_default: bool
    """Whether the parameter has a default value."""

    default: Any
    """The default value, if any."""

    default_repr: str
    """Python repr of the default value for code generation."""

    description: str | None = None
    """Description from schema."""


@dataclass
class JobVariableContext:
    """Processed job variable information for template rendering."""

    name: str
    """Safe Python identifier for the job variable."""

    original_name: str
    """Original job variable name from schema."""

    python_type: str
    """Python type annotation string."""

    description: str | None = None
    """Description from schema."""


@dataclass
class WorkPoolContext:
    """Processed work pool information for template rendering."""

    class_name: str
    """Generated TypedDict class name (e.g., 'KubernetesPoolJobVariables')."""

    original_name: str
    """Original work pool name."""

    fields: list[JobVariableContext]
    """List of job variable fields."""


@dataclass
class DeploymentContext:
    """Processed deployment information for template rendering."""

    class_name: str
    """Generated class name (e.g., '_MyEtlFlowProduction')."""

    full_name: str
    """Full deployment name (e.g., 'my-etl-flow/production')."""

    work_pool_name: str | None
    """Name of the work pool, if any."""

    description: str | None
    """Deployment description for docstring."""

    required_params: list[ParameterContext]
    """Required flow parameters."""

    optional_params: list[ParameterContext]
    """Optional flow parameters."""

    has_job_variables: bool
    """Whether this deployment has job variables to configure."""

    job_variable_fields: list[JobVariableContext]
    """List of job variable fields for with_infra() method."""


@dataclass
class TemplateContext:
    """Complete context for template rendering."""

    metadata: dict[str, Any]
    """Generation metadata."""

    module_name: str
    """Output module name (for docstring examples)."""

    deployment_names: list[str]
    """List of all deployment full names."""

    work_pool_typeddicts: list[WorkPoolContext]
    """Work pool TypedDict definitions."""

    deployments: list[DeploymentContext]
    """Deployment class definitions."""


@dataclass
class RenderResult:
    """Result of SDK rendering."""

    code: str
    """The generated Python code."""

    warnings: list[str] = field(default_factory=list)
    """Warnings generated during rendering."""


def _safe_repr(value: Any) -> str:
    """
    Generate a safe repr for a value that can be used in generated code.

    Handles common types that appear in JSON Schema defaults.
    """
    if value is None:
        return "None"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float, str)):
        return repr(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        # For non-empty lists, we need to recurse
        items = ", ".join(_safe_repr(item) for item in value)
        return f"[{items}]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        # For non-empty dicts, we need to recurse
        items = ", ".join(f"{_safe_repr(k)}: {_safe_repr(v)}" for k, v in value.items())
        return "{" + items + "}"
    # Fallback to repr
    return repr(value)


def _sanitize_docstring(text: str | None) -> str | None:
    """
    Sanitize text for use in docstrings.

    Handles edge cases like triple quotes that would break docstrings.
    """
    if text is None:
        return None
    # Replace triple quotes with single quotes
    text = text.replace('"""', "'''")
    # Strip leading/trailing whitespace
    return text.strip()


def _make_optional(python_type: str) -> str:
    """
    Make a type optional (add | None) if it isn't already nullable.

    Avoids redundant `str | None | None` patterns when the schema type
    is already nullable.
    """
    # Check if type already includes None
    # Handle both "T | None" and "None | T" patterns
    # Also handle "T | None | U" embedded patterns
    type_parts = [p.strip() for p in python_type.split("|")]
    if "None" in type_parts:
        return python_type
    return f"{python_type} | None"


def _process_fields_to_params(
    fields: list[FieldInfo],
    existing_identifiers: set[str],
) -> tuple[list[ParameterContext], list[ParameterContext]]:
    """
    Convert FieldInfo objects to ParameterContext objects.

    Returns (required_params, optional_params) tuple.
    """
    required: list[ParameterContext] = []
    optional: list[ParameterContext] = []

    for field_info in fields:
        # Generate safe identifier using deployment context to avoid 'self' collision
        safe_name = safe_identifier(field_info.name, existing_identifiers, "deployment")
        existing_identifiers.add(safe_name)

        param = ParameterContext(
            name=safe_name,
            original_name=field_info.name,
            python_type=field_info.python_type,
            required=field_info.required,
            has_default=field_info.has_default,
            default=field_info.default,
            default_repr=_safe_repr(field_info.default),
            description=field_info.description,
        )

        if field_info.required:
            required.append(param)
        else:
            optional.append(param)

    return required, optional


def _process_fields_to_job_variables(
    fields: list[FieldInfo],
    existing_identifiers: set[str],
) -> list[JobVariableContext]:
    """Convert FieldInfo objects to JobVariableContext objects."""
    result: list[JobVariableContext] = []

    for field_info in fields:
        # Generate safe identifier using deployment context to avoid 'self' collision
        safe_name = safe_identifier(field_info.name, existing_identifiers, "deployment")
        existing_identifiers.add(safe_name)

        result.append(
            JobVariableContext(
                name=safe_name,
                original_name=field_info.name,
                python_type=field_info.python_type,
                description=field_info.description,
            )
        )

    return result


def _process_work_pool(
    work_pool: WorkPoolInfo,
    existing_class_names: set[str],
) -> tuple[WorkPoolContext | None, list[str]]:
    """
    Process a work pool into template context.

    Returns (context, warnings) tuple. Returns None context if no fields.
    """
    warnings: list[str] = []

    # Extract fields from job variables schema
    schema = work_pool.job_variables_schema
    if not schema or not schema.get("properties"):
        return None, warnings

    fields, field_warnings = extract_fields_from_schema(schema)
    warnings.extend(field_warnings)

    if not fields:
        return None, warnings

    # Generate class name
    base_class_name = f"{work_pool.name}JobVariables"
    class_name = safe_class_name(base_class_name, existing_class_names)
    existing_class_names.add(class_name)

    # Process fields to job variables
    existing_identifiers: set[str] = set()
    job_vars = _process_fields_to_job_variables(fields, existing_identifiers)

    return (
        WorkPoolContext(
            class_name=class_name,
            original_name=work_pool.name,
            fields=job_vars,
        ),
        warnings,
    )


def _process_deployment(
    deployment: DeploymentInfo,
    work_pools: dict[str, WorkPoolInfo],
    processed_work_pools: dict[str, WorkPoolContext],
    existing_class_names: set[str],
) -> tuple[DeploymentContext, list[str]]:
    """
    Process a deployment into template context.

    Returns (context, warnings) tuple.
    """
    warnings: list[str] = []

    # Generate class name (underscore prefix for private class)
    # Combine flow name and deployment name for uniqueness
    base_name = f"{deployment.flow_name}_{deployment.name}"
    class_name = f"_{safe_class_name(base_name, existing_class_names)}"
    existing_class_names.add(class_name)

    # Process parameter schema
    required_params: list[ParameterContext] = []
    optional_params: list[ParameterContext] = []

    if deployment.parameter_schema:
        schema = deployment.parameter_schema
        fields, field_warnings = extract_fields_from_schema(schema)
        warnings.extend(field_warnings)

        existing_identifiers: set[str] = set()
        required_params, optional_params = _process_fields_to_params(
            fields, existing_identifiers
        )

    # Process job variables from work pool
    job_variable_fields: list[JobVariableContext] = []
    has_job_variables = False

    if deployment.work_pool_name:
        # Check if we have processed this work pool
        if deployment.work_pool_name in processed_work_pools:
            wp_context = processed_work_pools[deployment.work_pool_name]
            job_variable_fields = wp_context.fields
            has_job_variables = len(job_variable_fields) > 0
        elif deployment.work_pool_name in work_pools:
            # Work pool exists but has no job variables
            pass
        else:
            warnings.append(
                f"Work pool '{deployment.work_pool_name}' not found for deployment "
                f"'{deployment.full_name}'"
            )

    return (
        DeploymentContext(
            class_name=class_name,
            full_name=deployment.full_name,
            work_pool_name=deployment.work_pool_name,
            description=_sanitize_docstring(deployment.description),
            required_params=required_params,
            optional_params=optional_params,
            has_job_variables=has_job_variables,
            job_variable_fields=job_variable_fields,
        ),
        warnings,
    )


def build_template_context(
    data: SDKData,
    module_name: str,
) -> tuple[TemplateContext, list[str]]:
    """
    Convert SDKData to template-friendly context.

    Args:
        data: The SDK data from the API.
        module_name: The output module name (for docstring examples).

    Returns:
        A tuple of (TemplateContext, warnings).
    """
    warnings: list[str] = []
    existing_class_names: set[str] = set()

    # Process work pools first (deployments reference them)
    # Sort by name for deterministic output
    work_pool_typeddicts: list[WorkPoolContext] = []
    processed_work_pools: dict[str, WorkPoolContext] = {}

    for work_pool in sorted(data.work_pools.values(), key=lambda wp: wp.name):
        wp_context, wp_warnings = _process_work_pool(work_pool, existing_class_names)
        warnings.extend(wp_warnings)
        if wp_context:
            work_pool_typeddicts.append(wp_context)
            processed_work_pools[work_pool.name] = wp_context

    # Process deployments
    deployment_contexts: list[DeploymentContext] = []

    for deployment in data.all_deployments():
        dep_context, dep_warnings = _process_deployment(
            deployment,
            data.work_pools,
            processed_work_pools,
            existing_class_names,
        )
        warnings.extend(dep_warnings)
        deployment_contexts.append(dep_context)

    # Build metadata dict
    metadata = {
        "generation_time": data.metadata.generation_time,
        "prefect_version": data.metadata.prefect_version,
        "workspace_name": data.metadata.workspace_name,
        "api_url": data.metadata.api_url,
    }

    return (
        TemplateContext(
            metadata=metadata,
            module_name=module_name,
            deployment_names=data.deployment_names,
            work_pool_typeddicts=work_pool_typeddicts,
            deployments=deployment_contexts,
        ),
        warnings,
    )


def _get_template() -> jinja2.Template:
    """Load the SDK template from package resources.

    Uses importlib.resources for robust access in different installation layouts
    (editable installs, wheels, etc.).
    """
    # Use importlib.resources.files() for robust package resource access
    template_files = importlib.resources.files("prefect._sdk.templates")
    template_content = template_files.joinpath("sdk.py.jinja").read_text()

    # Create Jinja2 environment with safe defaults
    env = jinja2.Environment(
        autoescape=False,  # We're generating Python code, not HTML
        undefined=jinja2.StrictUndefined,  # Raise error on undefined variables
        keep_trailing_newline=True,  # Preserve trailing newline
    )

    # Add custom filters
    env.filters["repr"] = repr
    env.filters["make_optional"] = _make_optional

    return env.from_string(template_content)


def render_sdk(data: SDKData, output_path: Path) -> RenderResult:
    """
    Render the SDK template and write to file.

    Args:
        data: The SDK data from the API.
        output_path: Path to write the generated SDK file.

    Returns:
        RenderResult with the generated code and any warnings.
    """
    # Extract module name from output path
    module_name = output_path.stem

    # Build template context
    context, warnings = build_template_context(data, module_name)

    # Load and render template
    template = _get_template()
    code = template.render(
        metadata=context.metadata,
        module_name=context.module_name,
        deployment_names=context.deployment_names,
        work_pool_typeddicts=context.work_pool_typeddicts,
        deployments=context.deployments,
    )

    # Create parent directories if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write output file
    output_path.write_text(code)

    return RenderResult(code=code, warnings=warnings)


def render_sdk_to_string(data: SDKData, module_name: str = "sdk") -> RenderResult:
    """
    Render the SDK template to a string without writing to file.

    Args:
        data: The SDK data from the API.
        module_name: The module name for docstring examples.

    Returns:
        RenderResult with the generated code and any warnings.
    """
    # Build template context
    context, warnings = build_template_context(data, module_name)

    # Load and render template
    template = _get_template()
    code = template.render(
        metadata=context.metadata,
        module_name=context.module_name,
        deployment_names=context.deployment_names,
        work_pool_typeddicts=context.work_pool_typeddicts,
        deployments=context.deployments,
    )

    return RenderResult(code=code, warnings=warnings)
