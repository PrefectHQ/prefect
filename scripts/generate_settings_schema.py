import json

from prefect import __development_base_path__
from prefect.settings import Settings


def main():
    with open(__development_base_path__ / "schemas" / "settings_schema.json", "w") as f:
        json.dump(Settings.model_json_schema(), f, indent=4)


if __name__ == "__main__":
    main()
