"""
A class for configuring or automatically discovering settings to be used with PrefectDbtRunner.
"""

import contextlib
import tempfile
from pathlib import Path
from typing import Any, Generator

import yaml
from dbt_common.events.base_types import EventLevel
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from prefect.settings import get_current_settings
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.templating import (
    resolve_block_document_references,
    resolve_variables,
)
from prefect_dbt.utilities import find_profiles_dir, replace_with_env_var_call


class PrefectDbtSettings(BaseSettings):
    """
    dbt settings that directly affect the PrefectDbtRunner.
    These settings will be collected automatically from their corresponding 'DBT_'-prefixed environment variables.
    If a setting is not set in the environment or in the fields of this class, the default value will be used.

    All other dbt settings should be used as normal, e.g. in the dbt_project.yml file, env vars, or kwargs to `invoke()`.
    """

    model_config = SettingsConfigDict(env_prefix="DBT_")

    profiles_dir: Path = Field(
        default_factory=find_profiles_dir,
        description="The directory containing the dbt profiles.yml file.",
    )
    project_dir: Path = Field(
        default_factory=Path.cwd,
        description="The directory containing the dbt project.",
    )
    log_level: EventLevel = Field(
        default_factory=lambda: EventLevel(
            get_current_settings().logging.level.lower()
        ),
        description="The log level of the dbt CLI. Uses Prefect's logging level if not set.",
    )
    target_path: Path = Field(
        default=Path("target"),
        description="The path to the dbt target directory (relative to project_dir).",
    )

    def load_profiles_yml(self) -> dict[str, Any]:
        """
        Load and parse the profiles.yml file.

        Returns:
            Dict containing the parsed profiles.yml contents

        Raises:
            ValueError: If profiles.yml is not found
        """
        profiles_path = self.profiles_dir / "profiles.yml"
        if not profiles_path.exists():
            raise ValueError(f"No profiles.yml found at {profiles_path}")

        with open(profiles_path, "r") as f:
            return yaml.safe_load(f)

    @contextlib.contextmanager
    def resolve_profiles_yml(self) -> Generator[str, None, None]:
        """
        Context manager that creates a temporary directory with a resolved profiles.yml file.

        Args:
            include_profiles: Whether to include the resolved profiles.yml in the yield.

        Yields:
            str: Path to temporary directory containing the resolved profiles.yml.
                Directory and contents are automatically cleaned up after context exit.

        Example:
        ```python
            with resolve_profiles_yml() as temp_dir:
                # temp_dir contains resolved profiles.yml
                # use temp_dir for dbt operations
            # temp_dir is automatically cleaned up
        ```
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            profiles_yml: dict[str, Any] = self.load_profiles_yml()
            profiles_yml = run_coro_as_sync(
                resolve_block_document_references(
                    profiles_yml, value_transformer=replace_with_env_var_call
                )
            )
            profiles_yml = run_coro_as_sync(resolve_variables(profiles_yml))

            temp_profiles_path = temp_dir_path / "profiles.yml"
            temp_profiles_path.write_text(
                yaml.dump(profiles_yml, default_style=None, default_flow_style=False)
            )
            yield str(temp_dir_path)
