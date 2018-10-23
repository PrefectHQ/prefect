import os
from pathlib import Path

import click
import toml

PATH = os.path.join(os.getenv("HOME"), ".prefect/config.toml")


def load_prefect_config():
    config_data = toml.load(PATH) if Path(PATH).is_file() else None

    if not config_data:
        raise click.ClickException("CLI not configured. Run 'prefect configure init'")

    return config_data
