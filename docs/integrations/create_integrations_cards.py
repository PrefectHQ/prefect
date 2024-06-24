"""Script to generate the integrations (formerly integrations) catalog table"""

import glob
from pathlib import Path

import mkdocs_gen_files
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

with mkdocs_gen_files.open("./integrations/index.md", "w") as markdown_file:
    # Get file paths for all integrations files
    integration_files = [
        file
        for file in glob.glob("./docs/integrations/catalog/*.yaml")
        # Ignore the template file
        if Path(file).name != "TEMPLATE.yaml"
    ]

    # Load integration information from YAML files into a list
    integration_configs = []
    for integration_file in integration_files:
        with open(integration_file, "r") as file:
            integration_configs.append(yaml.safe_load(file))

    # Sort integrations alphabetically by name
    sorted_integration_configs = sorted(
        integration_configs, key=lambda x: x["tag"].lower()
    )

    tags = [config["tag"] for config in sorted_integration_configs]

    env = Environment(
        loader=FileSystemLoader("./"),
        autoescape=select_autoescape(enabled_extensions="html"),
    )
    template = env.get_template("index.md")

    # Use jinja2 template and in index.md and write out to index.html
    markdown_file.write(
        template.render(integrations=sorted_integration_configs, tags=tags)
    )
