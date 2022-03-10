"""Script to generate the collections catalog table"""
import glob
from pathlib import Path

import mkdocs_gen_files
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ITEMS_PER_ROW = 5

with mkdocs_gen_files.open("collections/catalog.md", "a") as markdown_file:
    collection_files = [
        file
        for file in glob.glob("./docs/collections/catalog/*.yaml")
        if Path(file).name != "TEMPLATE.yaml"
    ]

    collection_configs = []
    for collection_file in collection_files:
        with open(collection_file, "r") as file:
            collection_configs.append(yaml.safe_load(file))

    sorted_collection_configs = sorted(
        collection_configs, key=lambda x: x["collectionName"]
    )

    chunked_collection_configs = [
        sorted_collection_configs[i : i + ITEMS_PER_ROW]
        for i in range(0, len(collection_configs), ITEMS_PER_ROW)
    ]

    env = Environment(
        loader=FileSystemLoader("./docs/collections/templates/"),
        autoescape=select_autoescape(enabled_extensions="html"),
    )
    template = env.get_template("table.html")

    print(template.render(collections=sorted_collection_configs), file=markdown_file)
