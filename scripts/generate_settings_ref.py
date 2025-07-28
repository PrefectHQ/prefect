from typing import Any

from prefect import __development_base_path__
from prefect.settings import Settings


def resolve_ref(schema: dict[Any, Any], ref_path: str) -> dict[str, Any]:
    """Resolve a reference to a nested model."""
    return schema.get("$defs", {}).get(ref_path.split("/")[-1], {})


def build_ref_paths(schema: dict[Any, Any]) -> dict[str, str]:
    """Build a mapping of reference paths for all nested models."""
    paths: dict[str, str] = {}
    to_process: list[tuple[str, str, dict[Any, Any]]] = [("", "", schema)]

    defs = schema.get("$defs", {})

    while to_process:
        current_path, _, current_schema = to_process.pop(0)

        if "properties" in current_schema:
            for prop_name, prop_info in current_schema["properties"].items():
                new_path = f"{current_path}.{prop_name}" if current_path else prop_name

                if "$ref" in prop_info:
                    ref_name = prop_info["$ref"].split("/")[-1]
                    paths[ref_name] = new_path
                    if ref_name in defs:
                        to_process.append((new_path, ref_name, defs[ref_name]))

    return paths


def process_property_constraints(prop_info: dict[Any, Any]) -> list[str]:
    """Extract constraints from a property's schema information."""
    constraints: list[str] = []

    # Handle basic constraints
    for constraint in ["minimum", "maximum", "pattern", "enum"]:
        if constraint in prop_info:
            if constraint == "enum":
                constraints.append(
                    f"Allowed values: {', '.join(repr(v) for v in prop_info[constraint])}"
                )
            else:
                constraints.append(
                    f"{constraint.capitalize()}: {prop_info[constraint]}"
                )

    return constraints


def generate_property_docs(
    prop_name: str, prop_info: dict[Any, Any], level: int = 3, parent_path: str = ""
) -> str:
    """Generate documentation for a single property."""
    docs: list[str] = []
    header = "#" * level
    docs.append(f"{header} `{prop_name}`")

    # Description
    if "description" in prop_info:
        docs.append(f"{prop_info['description']}")

    # Type information
    if "$ref" in prop_info:
        ref_name = prop_info["$ref"].split("/")[-1]
        docs.append(f"\n**Type**: [{ref_name}](#{ref_name.lower()})")
    elif "type" in prop_info:
        prop_type = prop_info["type"]
        docs.append(f"\n**Type**: `{prop_type}`")
    elif "anyOf" in prop_info:
        # Handle complex type constraints
        types: list[str] = []
        for type_info in prop_info["anyOf"]:
            if "type" in type_info:
                if type_info["type"] == "null":
                    types.append("None")
                else:
                    types.append(type_info["type"])
        if types:
            docs.append(f"\n**Type**: `{' | '.join(types)}`")
        else:
            docs.append("\n**Type**: `any`")
    else:
        docs.append("\n**Type**: `any`")

    # Default value
    if "default" in prop_info:
        docs.append(f"\n**Default**: `{prop_info['default']}`")

    # Examples
    if "examples" in prop_info:
        docs.append("\n**Examples**:")
        for example in prop_info["examples"]:
            if isinstance(example, str):
                docs.append(f'- `"{example}"`')
            elif isinstance(example, dict):
                docs.append(f"- `{example}`")
            else:
                docs.append(f"- `{example}`")

    # Constraints
    constraints = process_property_constraints(prop_info)
    if constraints:
        docs.append("\n**Constraints**:")
        for constraint in constraints:
            docs.append(f"- {constraint}")

    # Access path
    access_path = f"{parent_path}.{prop_name}" if parent_path else prop_name
    docs.append(f"\n**TOML dotted key path**: `{access_path}`")

    if supported_env_vars := prop_info.get("supported_environment_variables"):
        docs.append("\n**Supported environment variables**:")
        docs.append(", ".join(f"`{env_var}`" for env_var in supported_env_vars))

    return "\n".join(docs) + "\n"


def generate_model_docs(
    schema: dict[Any, Any], level: int = 1, parent_path: str = ""
) -> str:
    """Generate documentation for a model and its properties."""
    docs: list[str] = []
    header = "#" * level

    if not schema.get("properties"):
        return ""

    # Model title and description
    title = schema.get("title", "Settings")
    docs.append(f"{header} {title}")

    if "description" in schema:
        docs.append(f"{schema['description']}")

    # Process all properties
    if "properties" in schema:
        for prop_name, prop_info in schema["properties"].items():
            docs.append(
                generate_property_docs(
                    prop_name, prop_info, level=level + 1, parent_path=parent_path
                )
            )

    docs.append("---")

    return "\n".join(docs)


def process_definitions(defs: dict[Any, Any], schema: dict[Any, Any]) -> str:
    """Process all model definitions and generate their documentation."""
    docs: list[str] = []

    # Build complete reference paths
    ref_paths = build_ref_paths(schema)

    docs.append("---")
    for model_name, model_schema in defs.items():
        parent_path = ref_paths.get(model_name, "")
        docs.append(generate_model_docs(model_schema, level=2, parent_path=parent_path))

    return "\n".join(docs)


def main():
    schema = Settings.model_json_schema()
    # Generate main documentation
    docs_content: list[str] = [
        "---",
        "title: Settings reference",
        "description: Reference for all available settings for Prefect.",
        "---",
        "{/* This page is generated by `scripts/generate_settings_ref.py`. Update the generation script to update this page. */}",
        "<Note>To use `prefect.toml` or `pyproject.toml` for configuration, `prefect>=3.1` must be installed.</Note>",
        "## Root Settings",
    ]

    # Generate documentation for top-level properties
    if "properties" in schema:
        for prop_name, prop_info in schema["properties"].items():
            if "$ref" in prop_info and not resolve_ref(schema, prop_info["$ref"]).get(
                "properties"
            ):
                # Exclude nested models with no properties (like `experiments` sometimes)
                continue
            docs_content.append(generate_property_docs(prop_name, prop_info, level=3))

    # Generate documentation for nested models
    if "$defs" in schema:
        docs_content.append(process_definitions(schema["$defs"], schema))

    with open(
        __development_base_path__ / "docs" / "v3" / "api-ref" / "settings-ref.mdx",
        "w",
    ) as f:
        f.write("\n".join(docs_content))


if __name__ == "__main__":
    main()
