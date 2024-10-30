import json

from prefect import __development_base_path__
from prefect.server.api.server import create_app


def main():
    app = create_app()
    openapi_schema = app.openapi()

    with open(__development_base_path__ / "schemas" / "openapi.schema.json", "w") as f:
        # Remove the version from the info object because we use the package version
        # which changes frequently
        openapi_schema["info"].pop("version", None)
        json.dump(openapi_schema, f, indent=4)


if __name__ == "__main__":
    main()
