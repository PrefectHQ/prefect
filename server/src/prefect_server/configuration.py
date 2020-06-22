# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license

import os

import prefect_server
from prefect.configuration import load_configuration

DEFAULT_CONFIG = os.path.join(os.path.dirname(prefect_server.__file__), "config.toml")
USER_CONFIG = os.getenv(
    "PREFECT_SERVER__USER_CONFIG_PATH", "~/.prefect_server/config.toml"
)
ENV_VAR_PREFIX = "PREFECT_SERVER"


config = load_configuration(
    path=DEFAULT_CONFIG, user_config_path=USER_CONFIG, env_var_prefix=ENV_VAR_PREFIX
)
