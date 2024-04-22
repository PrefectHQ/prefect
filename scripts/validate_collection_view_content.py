import json
from pathlib import Path
from typing import Literal

import fastjsonschema

EXCLUDE_TYPES = {"demo-flow"}

CollectionViewVariety = Literal["flow", "worker", "block"]

flow_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "slug": {"type": "string"},
        "parameters": {"type": "object"},
        "description": {"type": "object"},
        "documentation_url": {"type": "string"},
        "logo_url": {"type": "string"},
        "install_command": {"type": "string"},
        "path_containing_flow": {"type": "string"},
        "entrypoint": {"type": "string"},
        "repo_url": {"type": "string"},
    },
    "required": [
        "name",
        "slug",
        "parameters",
        "description",
        "documentation_url",
        "logo_url",
        "install_command",
        "path_containing_flow",
        "entrypoint",
        "repo_url",
    ],
}

worker_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "type": {"type": "string"},
        "description": {"type": "string"},
        "display_name": {"type": "string"},
        "documentation_url": {"type": "string"},
        "logo_url": {"type": "string"},
        "install_command": {"type": "string"},
        "default_base_job_configuration": {"type": "object"},
        "is_beta": {"type": "boolean"},
    },
    "required": [
        "type",
        "description",
        "install_command",
        "default_base_job_configuration",
    ],
}

block_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "slug": {"type": "string"},
        "logo_url": {
            "minLength": 1,
            "maxLength": 2083,
            "format": "uri",
            "type": "string",
        },
        "documentation_url": {
            "minLength": 1,
            "maxLength": 2083,
            "format": "uri",
            "oneOf": [{"type": "string"}, {"type": "null"}],
        },
        "description": {"type": "string"},
        "code_example": {"type": "string"},
        "block_schema": {"$ref": "#/components/schemas/block_schema"},
    },
    "required": [
        "name",
        "slug",
        "logo_url",
        "description",
        "code_example",
        "block_schema",
    ],
    "components": {
        "schemas": {
            "block_schema": {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {
                    "checksum": {"type": "string"},
                    "version": {"type": "string"},
                    "capabilities": {"type": "array", "items": {"type": "string"}},
                    "fields": {"type": "object"},
                },
                "required": [
                    "checksum",
                    "version",
                    "capabilities",
                    "fields",
                ],
            }
        }
    },
}


def validate_view_content(view_dict: dict, variety: CollectionViewVariety) -> None:
    """Raises an error if the view content is not valid."""

    if variety == "flow":
        schema = flow_schema
    elif variety == "worker":
        schema = worker_schema
    elif variety == "block":
        schema = block_schema
    else:
        raise ValueError(f"Invalid variety: {variety}")

    validate = fastjsonschema.compile(schema)

    for collection_name, collection_metadata in view_dict.items():
        if variety == "block":
            collection_metadata = collection_metadata["block_types"]
        try:
            # raise validation errors if any metadata doesn't match the schema
            list(map(validate, collection_metadata.values()))
        except IndexError:  # to catch something like {"prefect-X": {}}
            raise ValueError("There's a key with empty value in this view!")
        print(f"  Validated {collection_name} summary in {variety} view!")


if __name__ == "__main__":
    included_paths = [
        (
            "worker",
            "src/prefect/server/api/collections_data/views/aggregate-worker-metadata.json",
        )
    ]

    for variety, file in included_paths:
        path = Path(file)
        if any(exclude in path.name for exclude in EXCLUDE_TYPES):
            continue

        print(f"validating {path.stem} ...")

        view_dict = json.loads(path.read_text())
        validate_view_content(view_dict, variety)
