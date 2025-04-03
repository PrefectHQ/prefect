#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from packaging.version import Version

from prefect.server.api.server import create_app

Mint = dict[str, Any]
Navigation = list[dict[str, Any]]
SinglePage = str
PageGroup = dict[str, Any]

MINTLIFY_SCRAPE = ["npx", "--yes", "@mintlify/scraping@3.0.123"]


def docs_path() -> Path:
    return Path(__file__).parent.parent / "docs"


"""Load the overall Mintlify configuration file"""
with open(docs_path() / "docs.json", "r") as f:
    docs_json = json.load(f)


def current_version() -> str:
    """
    Return a high-level version string for the current Prefect version,
    such as "3" or "3.1.0rc".
    """

    version = Version("3.0.0")
    return f"v{version.major}{version.minor if version.pre else ''}{version.pre[0] if version.pre else ''}"


def main():
    ensure_npx_environment()

    version = current_version()
    server_docs_path = docs_path() / f"{version}/api-ref/rest-api/server/"

    suggestions = generate_schema_documentation(version, server_docs_path)

    # Find the "Server API" section and replace the "pages" content other than the index
    for tab in docs_json["navigation"]["tabs"]:
        if tab["tab"] == "API Reference":
            for group in tab["groups"]:
                if group["group"] == "API Reference":
                    for page in group["pages"]:
                        if isinstance(page, dict) and page["group"] == "REST API":
                            for rest_group in page["pages"]:
                                if (
                                    isinstance(rest_group, dict)
                                    and rest_group["group"] == "Server API"
                                ):
                                    rest_group["pages"][1:] = suggestions

    # Write out the updated docs.json file
    write_docs(docs_json)


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

    # Omit UI routes from the OpenAPI to avoid including them in the docs.
    # UI routes are not intended to be used by users.
    for path in list(openapi_schema["paths"].keys()):
        if path.startswith("/api/ui/"):
            print("Dropping UI route:", path)
            del openapi_schema["paths"][path]

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


def write_docs(updated_docs_json: Mint):
    """Write updated docs.json file out"""
    with open(docs_path() / "docs.json", "w") as f:
        json.dump(updated_docs_json, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
