"""Script to generate the collections catalog table"""
import glob
from pathlib import Path

import mkdocs_gen_files
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

with mkdocs_gen_files.open("collections/catalog.md", "w") as markdown_file:
    # Get file paths for all collections files
    collection_files = [
        file
        for file in glob.glob("./docs/collections/catalog/*.yaml")
        # Ignore the template file
        if Path(file).name != "TEMPLATE.yaml"
    ]

    # Load collection information from YAML files into a list
    collection_configs = []
    for collection_file in collection_files:
        with open(collection_file, "r") as file:
            collection_configs.append(yaml.safe_load(file))

    # Sort collections alphabetically by name
    sorted_collection_configs = sorted(
        collection_configs, key=lambda x: x["tag"].lower()
    )

    tags = [config["tag"] for config in sorted_collection_configs]

    env = Environment(
        loader=FileSystemLoader("./docs/collections/"),
        autoescape=select_autoescape(enabled_extensions="html"),
    )
    template = env.get_template("catalog.md")

    # Render jinja2 template and write to catalog.md
    markdown_file.write(
        template.render(collections=sorted_collection_configs, tags=tags)
    )
