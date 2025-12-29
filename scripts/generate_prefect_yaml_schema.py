import json
from typing import Any

from pydantic.json_schema import GenerateJsonSchema

from prefect import __development_base_path__
from prefect.cli.deploy._models import PrefectYamlModel


def strip_titles(obj: Any) -> Any:
    """Remove auto-generated 'title' fields from schema to clean up IDE display."""
    if isinstance(obj, dict):
        return {k: strip_titles(v) for k, v in obj.items() if k != "title"}
    elif isinstance(obj, list):
        return [strip_titles(item) for item in obj]
    return obj


class PrefectYamlGenerateJsonSchema(GenerateJsonSchema):
    def generate(self, schema, mode="validation"):
        json_schema = super().generate(schema, mode=mode)
        json_schema = strip_titles(json_schema)
        json_schema["title"] = "Prefect YAML"
        json_schema["$schema"] = self.schema_dialect
        json_schema["$id"] = (
            "https://github.com/PrefectHQ/prefect/schemas/prefect.yaml.schema.json"
        )
        return json_schema


def main():
    with open(
        __development_base_path__ / "schemas" / "prefect.yaml.schema.json", "w"
    ) as f:
        json.dump(
            PrefectYamlModel.model_json_schema(
                schema_generator=PrefectYamlGenerateJsonSchema
            ),
            f,
            indent=4,
        )


if __name__ == "__main__":
    main()
