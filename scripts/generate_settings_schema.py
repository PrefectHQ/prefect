import json

from pydantic.json_schema import GenerateJsonSchema

from prefect import __development_base_path__
from prefect.settings import Settings


class SettingsGenerateJsonSchema(GenerateJsonSchema):
    def generate(self, schema, mode="validation"):
        json_schema = super().generate(schema, mode=mode)
        json_schema["title"] = "Prefect Settings"
        json_schema["$schema"] = self.schema_dialect
        json_schema["$id"] = (
            "https://github.com/PrefectHQ/prefect/schemas/settings.schema.json"
        )
        return json_schema


def main():
    with open(__development_base_path__ / "schemas" / "settings.schema.json", "w") as f:
        json.dump(
            Settings.model_json_schema(schema_generator=SettingsGenerateJsonSchema),
            f,
            indent=4,
        )


if __name__ == "__main__":
    main()
