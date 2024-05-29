"""
This script removes aliases from the versions.json file because `mike` does not
reliable change the `latest` alias to only point to the newest version when
adding or removing versions. Removing the aliases before building a new docs
makes it easy to add the alias to the correct version after the docs are built.
"""
import argparse
import json


def get_versions_json(file_path):
    """Accepts a file path for versions.json and returns a dict containing
    the versions JSON file.

    Args:
        file_path (str): A file path for versions.json

    Returns:
        list: A list of dicts containing version information
    """
    with open(file_path, "r") as f:
        return json.load(f)


def save_versions_json(versions_json, file_path):
    """Accepts a list containing versions json dicts and a file path for
    the versions json file and saves it to a JSON file.

    Args:
        versions_json (list): A list of dicts containing version information
        file_path (str): A file path for the versions json file
    """
    with open(file_path, "w") as f:
        json.dump(versions_json, f, indent=4)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--versions-file-path",
        help="The path to the versions.json file",
    )

    args = parser.parse_args()

    versions_json = get_versions_json(args.versions_file_path)

    # set the "aliases" key to an empty list for each version
    for version in versions_json:
        version["aliases"] = []

    save_versions_json(versions_json, args.versions_file_path)
