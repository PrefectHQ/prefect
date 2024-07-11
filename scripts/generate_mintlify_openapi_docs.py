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

    # Find the "Server API" section and replace the "pages" content other than the index
    for group in mint_json["navigation"]:
        if group["group"] == "APIs & SDK" and group["version"] == version:
            for sub_group in group["pages"]:
                if isinstance(sub_group, dict) and sub_group["group"] == "REST API":
                    for rest_group in sub_group["pages"]:
                        if (
                            isinstance(rest_group, dict)
                            and rest_group["group"] == "Server API"
                        ):
                            rest_group["pages"][1:] = suggestions

    # Write out the updated mint.json file
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


def write_mint(update_mint_json: Mint):
    """Write updated mint.json file out"""
    with open(docs_path() / "mint.json", "w") as f:
        json.dump(update_mint_json, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
