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
        # Recursively update all default values to use forward slashes
        self._normalize_path_separators(json_schema)
        return json_schema

    def _normalize_path_separators(self, obj):
        """Recursively update all string values that look like paths to use forward slashes."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and ("\\" in value or "/" in value):
                    # Replace backslashes with forward slashes
                    obj[key] = value.replace("\\", "/")
                elif isinstance(value, (dict, list)):
                    self._normalize_path_separators(value)
        elif isinstance(obj, list):
            for i, value in enumerate(obj):
                if isinstance(value, str) and ("\\" in value or "/" in value):
                    # Replace backslashes with forward slashes
                    obj[i] = value.replace("\\", "/")
                elif isinstance(value, (dict, list)):
                    self._normalize_path_separators(value)


def main():
    with open(__development_base_path__ / "schemas" / "settings.schema.json", "w") as f:
        json.dump(
            Settings.model_json_schema(schema_generator=SettingsGenerateJsonSchema),
            f,
            indent=4,
        )


if __name__ == "__main__":
    main()
