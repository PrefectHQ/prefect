#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Union

from prefect.server.api.server import create_app

Mint = dict[str, Any]
Navigation = list[dict[str, Any]]
SinglePage = str
PageGroup = dict[str, Any]


def docs_path() -> Path:
    return Path(__file__).parent.parent / "docs"


def current_version() -> str:
    # TODO: derive this from the docs and the current version of the prefect package
    return "3.0rc"


def main():
    ensure_mintlify_installed()

    version = current_version()
    server_docs_path = docs_path() / f"{version}/api-ref/server/"

    suggestions = generate_schema_documentation(version, server_docs_path)

    mint_json, current_navigation = load_mint_and_server_navigation(version)

    # Add any additional pages that are not generated from the schema but that we
    # definitely want to include, like the main index page
    keepers = {f"{version}/api-ref/server/index"}

    merge_suggestions(current_navigation, suggestions, keepers)

    remove_orphaned_pages(server_docs_path, current_navigation)

    write_mint(mint_json)


def ensure_mintlify_installed():
    result = subprocess.run(["which", "mintlify-scrape"])
    if result.returncode == 0:
        return

    result = subprocess.run(["which", "npm"])
    if result.returncode != 0:
        print(
            "Neither `@mintlify/scraping` nor `npm` are installed.  Please make sure "
            "you have a working `npm` installation before generating API docs.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("@mintlify/scraping is not installed. Installing...")
    subprocess.check_call(["npm", "install", "-g", "@mintlify/scraping"])


def generate_schema_documentation(version: str, server_docs_path: Path) -> Navigation:
    """Write the current OpenAPI schema to the given path, generates documentation files
    from it, then returns Mintlify's recommended navigation updates."""
    openapi_schema = create_app().openapi()
    openapi_schema["info"]["version"] = version

    schema_path = server_docs_path / "schema.json"
    with open(schema_path, "w") as f:
        json.dump(openapi_schema, f, indent=4, ensure_ascii=False)
        f.flush()

    result = subprocess.run(
        [
            "mintlify-scrape",
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
    suggestions = json.loads(output)
    return suggestions


def load_mint_and_server_navigation(version: str) -> tuple[Mint, Navigation]:
    """Loads the overall Mintlify configuration and finds (or creates) the navigation
    entry for the Server API REST documentation for the given version"""

    with open(docs_path() / "mint.json", "r") as f:
        mint_json = json.load(f)

    for group in mint_json["navigation"]:
        if group["group"] == "Server API" and group["version"] == version:
            return mint_json, group["pages"]

    current_navigation = {
        "group": "Server API",
        "version": version,
        "pages": [],
    }
    mint_json["navigation"].append(current_navigation)

    return mint_json, current_navigation["pages"]


def merge_suggestions(
    current_navigation: Navigation, suggestions: Navigation, keepers: set[SinglePage]
):
    """Merges the suggestions into the current navigation, updating the current
    navigation in-place"""
    suggestions_by_group: dict[str, Union[PageGroup, SinglePage]] = {
        suggestion["group"] if isinstance(suggestion, dict) else suggestion: suggestion
        for suggestion in suggestions
    }
    current_by_group: dict[str, Union[PageGroup, SinglePage]] = {
        item["group"] if isinstance(item, dict) else item: item
        for item in current_navigation
    }

    for group, suggestion in suggestions_by_group.items():
        if group not in current_by_group:
            current_navigation.append(suggestion)
        else:
            current = current_by_group[group]
            if current == suggestion:
                continue

            current["pages"] = suggestion["pages"]

    for group, current in current_by_group.items():
        if group not in suggestions_by_group and group not in keepers:
            current_navigation.remove(current)


def remove_orphaned_pages(server_docs_path: Path, current_navigation: Navigation):
    """Removes any pages that are not in the current navigation from the docs directory"""
    all_desired_pages = set()
    for item in current_navigation:
        if isinstance(item, dict):
            all_desired_pages.update(item["pages"])
        else:
            all_desired_pages.add(item)

    for page in server_docs_path.glob("**/*.mdx"):
        page_file = Path(page)
        page_path = page_file.relative_to(docs_path()).with_suffix("")
        if str(page_path) not in all_desired_pages:
            page_file.unlink()


def write_mint(mint_json):
    with open(docs_path() / "mint.json", "w") as f:
        json.dump(mint_json, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
