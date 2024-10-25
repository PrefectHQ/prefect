from typing import Any, Dict

from prefect import __development_base_path__
from prefect.settings import Settings


def process_property_constraints(prop_info: Dict[Any, Any]) -> list:
    """Extract constraints from a property's schema information."""
    constraints = []

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

    # Handle complex type constraints
    if "anyOf" in prop_info:
        types = []
        for type_info in prop_info["anyOf"]:
            if "type" in type_info:
                types.append(type_info["type"])
            if "format" in type_info:
                types.append(f"format: {type_info['format']}")
        if types:
            constraints.append(f"Accepts: {' or '.join(types)}")

    return constraints


def generate_property_docs(
    prop_name: str, prop_info: Dict[Any, Any], level: int = 3
) -> str:
    """Generate documentation for a single property."""
    docs = []
    header = "#" * level
    docs.append(f"{header} {prop_name}")

    # Type information
    if "$ref" in prop_info:
        ref_name = prop_info["$ref"].split("/")[-1]
        docs.append(f"**Type**: [{ref_name}](#{ref_name.lower()})")
    else:
        prop_type = prop_info.get("type", "any")
        docs.append(f"**Type**: `{prop_type}`")

    # Description
    if "description" in prop_info:
        docs.append(f"\n{prop_info['description']}")

    # Default value
    if "default" in prop_info:
        docs.append(f"\n**Default**: `{prop_info['default']}`")

    # Constraints
    constraints = process_property_constraints(prop_info)
    if constraints:
        docs.append("\n**Constraints**:")
        for constraint in constraints:
            docs.append(f"- {constraint}")

    return "\n".join(docs) + "\n"


def generate_model_docs(schema: Dict[Any, Any], level: int = 1) -> str:
    """Generate documentation for a model and its properties."""
    docs = []
    header = "#" * level

    # Model title and description
    title = schema.get("title", "Settings")
    docs.append(f"{header} {title}\n")

    if "description" in schema:
        docs.append(f"{schema['description']}\n")

    # Process all properties
    if "properties" in schema:
        docs.append(f"{header}{'#'} Properties\n")
        for prop_name, prop_info in schema["properties"].items():
            docs.append(generate_property_docs(prop_name, prop_info, level + 2))

    return "\n".join(docs)


def process_definitions(defs: Dict[Any, Any]) -> str:
    """Process all model definitions and generate their documentation."""
    docs = []

    for model_name, model_schema in defs.items():
        docs.append(generate_model_docs(model_schema, level=2))
        docs.append("\n---\n")

    return "\n".join(docs)


def main():
    schema = Settings.model_json_schema()
    # Generate main documentation
    docs_content = [
        "---",
        "title: Settings reference",
        "description: Reference for all available settings for Prefect.",
        "---",
        "## Root Settings",
        "### Properties",
    ]

    # Generate documentation for top-level properties
    if "properties" in schema:
        for prop_name, prop_info in schema["properties"].items():
            docs_content.append(generate_property_docs(prop_name, prop_info, level=4))

    # Generate documentation for nested models
    if "$defs" in schema:
        docs_content.append(process_definitions(schema["$defs"]))

    with open(
        __development_base_path__ / "docs" / "3.0" / "develop" / "settings-ref.mdx",
        "w",
    ) as f:
        f.write("\n".join(docs_content))


if __name__ == "__main__":
    main()
