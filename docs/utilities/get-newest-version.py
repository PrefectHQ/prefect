"""
This script is used to determine the newest version of the docs by comparing
all versions in the versions.json file plus the version being built to determine
which is the newest version. The build action uses the output of this script

"""
import argparse
import json

from packaging.version import parse as parseVersion


def get_versions_json(file_path: str) -> "list[dict]":
    """Accepts a file path for versions.json and returns a dict containing
    the versions JSON file.

    Args:
        file_path (str): A file path for versions.json

    Returns:
        list: A list of dicts containing version information
    """
    with open(file_path, "r") as f:
        return json.load(f)


def get_newest_version(versions: "list[dict]", build_version: str) -> str:
    """Accepts a list containing versions json dicts and sorts the
    versions in descending order.

    Args:
        versions (list): A list of dicts containing version information
    Returns:
        dict: A dict containing the versions JSON file with sorted versions
    """
    excluded_versions = ["latest", "unreleased", "mkdocs"]

    if len(versions) == 0:
        return build_version

    # remove the "latest" and "unreleased" versions from the list if they are present
    # since they will break version sorting, and we don't want to include them in
    # determining the newest version anyway.
    versions: "list[str]" = [
        version["version"]
        for version in versions
        if version["version"] not in excluded_versions
    ]

    if build_version not in excluded_versions:
        versions.append(build_version)

    # use sorted() to sort the versions in descending order
    sorted_versions = sorted(
        versions,
        key=parseVersion,
        reverse=True,
    )

    # the newest version is the first item in the sorted list
    return sorted_versions[0]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--versions-file-path",
        help="The path to the versions.json file",
    )
    parser.add_argument(
        "--build-version",
        help="The version of the docs being built",
    )
    args = parser.parse_args()

    versions_json = get_versions_json(args.versions_file_path)
    newest_version = get_newest_version(versions_json, args.build_version)
    print(newest_version)
