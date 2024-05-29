"""
This script sorts the versions in the versions.json file in descending order.

It's needed because the version selector `mike` adds to the docs UI outputs the versions
in the order they are listed in the versions.json file, but `mike` does not sort the
versions in sort-docs-versions.py after building the docs.
"""
import argparse
import json

from packaging.version import parse as parseVersion

HIDE_UNRELEASED_VERSION = False


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


def sort_versions_json(versions):
    """Accepts a list containing versions json dicts and sorts the
    versions in descending order.

    Args:
        versions (list): A list of dicts containing version information
    Returns:
        dict: A dict containing the versions JSON file with sorted versions
    """
    if HIDE_UNRELEASED_VERSION:
        # Remove the "unreleased" version from the list if necessary.
        # This will not prevent "unreleased" docs from being added built,
        # but it will prevent them from being added to the version selector.
        versions = [
            version for version in versions if version["version"] != "unreleased"
        ]

    invalid_versions_count = 0

    def sort_key(version):
        nonlocal invalid_versions_count
        """ Uses the `parseVersion` function from the `packaging` module to 
        parse a version string into a Version object if possible, 
        otherwise returns a dummy Version that ensures the version will be added
        to the end of the list
        """
        try:
            return parseVersion(version["version"])
        except ValueError:
            invalid_versions_count += 1
            return parseVersion("0.0.0")

    # use sorted() to sort the versions in descending order
    sorted_versions = sorted(
        versions,
        key=sort_key,
        reverse=True,
    )

    # iterate over the sorted versions and set the "aliases" key to an empty list
    for version in sorted_versions:
        version["aliases"] = []

    # then, add the "latest" alias to the first version
    sorted_versions[0]["aliases"].append("latest")

    # if any invalid versions were found, sort them in alphabetical order
    # and update the list of versions since they are already added to the
    # end of the list.
    if invalid_versions_count > 0:
        # get the last n elements from the list where n is the number of
        # invalid versions
        invalid_versions = sorted_versions[-invalid_versions_count:]

        # remove the invalid versions from the list
        sorted_versions = sorted_versions[:-invalid_versions_count]

        # sort the invalid versions in alphabetical order
        invalid_versions = sorted(invalid_versions, key=sort_key)

        # re-add the invalid versions to the list
        sorted_versions.extend(invalid_versions)

    return sorted_versions


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
    updated_versions = sort_versions_json(versions_json)
    save_versions_json(updated_versions, args.versions_file_path)
