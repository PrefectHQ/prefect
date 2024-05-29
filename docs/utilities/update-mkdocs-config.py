"""
This script adds the docs version to the mkdocs config so we can render
version numbers in docs templates. `mike` is supposed to do this, but it
did not work as documented as of April 2023.
"""
import argparse

import yaml


def get_mkdocs_config(file_path):
    """Accepts a file path for mkdocs.yml and returns a dict containing
    the mkdocs config.

    Args:
        file_path (str): A file path for mkdocs.yml

    Returns:
        dict: A dict containing the mkdocs config
    """
    with open(file_path, "r") as f:
        return yaml.load(f.read(), Loader=yaml.BaseLoader)


def save_mkdocs_config(mkdocs_config, file_path):
    """Accepts a dict containing the mkdocs config and a file path for
    the mkdocs config and saves it to a YAML file.

    Args:
        mkdocs_config (dict): A dict containing the mkdocs config
        file_path (str): A file path for the mkdocs config
    """
    with open(file_path, "w") as f:
        yaml.dump(mkdocs_config, f, default_flow_style=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config-file-path",
        help="The path to the mkdocs config file",
    )
    parser.add_argument(
        "--docs-version",
        help="The docs version to set in the mkdocs config",
    )

    args = parser.parse_args()

    # Update the version so we can render version numbers in docs templates.
    mkdocs_config = get_mkdocs_config(args.config_file_path)
    mkdocs_config["extra"]["version"] = args.docs_version
    save_mkdocs_config(mkdocs_config, args.config_file_path)
