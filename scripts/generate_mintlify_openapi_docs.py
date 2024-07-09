#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from packaging.version import Version

import prefect
from prefect.server.api.server import create_app

Mint = dict[str, Any]
Navigation = list[dict[str, Any]]
SinglePage = str
PageGroup = dict[str, Any]

MINTLIFY_SCRAPE = ["npx", "--yes", "@mintlify/scraping@3.0.123"]


def docs_path() -> Path:
    return Path(__file__).parent.parent / "docs"


"""Load the overall Mintlify configuration file"""
with open(docs_path() / "mint.json", "r") as f:
    mint_json = json.load(f)


def current_version() -> str:
    """
    Return a high-level version string for the current Prefect version,
    such as "3.1" or "3.1rc".
    """
    version = Version(prefect.__version__)
    return f"{version.major}.{version.minor}{version.pre[0] if version.pre else ''}"


def main():
    ensure_npx_environment()

    version = current_version()
    server_docs_path = docs_path() / f"{version}/api-ref/rest-api/server/"

    suggestions = generate_schema_documentation(version, server_docs_path)

    # Search for the "Server API" group and get its path and contents
    server_api_path, server_api_contents = search_group(mint_json, "Server API")

    if (
        server_api_path
        and "pages" in server_api_contents
        and len(server_api_contents["pages"]) > 1
    ):
        server_api_path.append(("pages", server_api_contents["pages"]))
        server_api_contents["pages"][1:] = suggestions

        # Replace the contents at the path with the new JSON
        set_value_at_path(mint_json, server_api_path, server_api_contents["pages"])

        # Write the updated mint.json file out
        write_mint(mint_json)


def ensure_npx_environment():
    result = subprocess.run(["which", "npx"], capture_output=True)
    if result.returncode != 0:
        print(
            "`npx` is not installed.  Please make sure you have a working `npm` "
            "installation before generating API docs.",
            file=sys.stderr,
        )
        sys.exit(1)


def generate_schema_documentation(version: str, server_docs_path: Path) -> Navigation:
    """Writes the current OpenAPI schema to the given path, generates documentation files
    from it, then returns Mintlify's recommended navigation updates."""
    openapi_schema = create_app().openapi()
    openapi_schema["info"]["version"] = version

    schema_path = server_docs_path / "schema.json"
    with open(schema_path, "w") as f:
        json.dump(openapi_schema, f, indent=4, ensure_ascii=False)
        f.flush()

    result = subprocess.run(
        MINTLIFY_SCRAPE
        + [
            "openapi-file",
            schema_path,
            "-o",
            server_docs_path.relative_to(docs_path()),
        ],
        cwd=docs_path(),
        stdout=subprocess.PIPE,
        encoding="utf-8",
        check=True,
    )

    # mintlify-scrape will output a list of suggestions for navigation objects, prefixed
    # with a header "navigation object suggestion:"
    output = result.stdout.replace("navigation object suggestion:\n", "")
    try:
        suggestions = json.loads(output)
    except Exception:
        print("Couldn't understand the output of mintlify-scrape:", file=sys.stderr)
        print(output, file=sys.stderr)
        raise
    return suggestions


def search_group(json_obj, search_key, path=None):
    """Search for a specific group in JSON and return the path and contents"""
    if path is None:
        path = []
    if isinstance(json_obj, dict):
        if json_obj.get("group") == search_key:
            return path, json_obj
        for key, value in json_obj.items():
            new_path = path + [(key, value)]
            if isinstance(value, (dict, list)):
                result = search_group(value, search_key, new_path)
                if result[0]:
                    return result
    elif isinstance(json_obj, list):
        for index, item in enumerate(json_obj):
            new_path = path + [(index, item)]
            result = search_group(item, search_key, new_path)
            if result[0]:
                return result
    return None, None


def set_value_at_path(json_obj, path, new_value):
    """Set a value in a JSON object at a specific path"""
    for key, value in path[:-1]:
        if isinstance(key, int):
            json_obj = json_obj[key]
        else:
            json_obj = json_obj[key]
    last_key = path[-1][0]
    if isinstance(last_key, int):
        json_obj[last_key] = new_value
    else:
        json_obj[last_key] = new_value


# Replace the contents at the path with the new JSON
def write_mint(main_data):
    """Write updated mint.json file out"""
    with open(docs_path() / "mint.json", "w") as f:
        json.dump(main_data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
