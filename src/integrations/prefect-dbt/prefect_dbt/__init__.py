from . import _version

from .core import PrefectDbtSettings, PrefectDbtRunner
from .cloud import DbtCloudCredentials, DbtCloudJob

# Define the mapping of CLI-related attributes to their import locations
_public_api: dict[str, tuple[str, str]] = {
    "DbtCliProfile": ("prefect_dbt", "cli"),
    "GlobalConfigs": ("prefect_dbt", "cli"),
    "MissingExtrasRequireError": ("prefect_dbt", "cli"),
    "TargetConfigs": ("prefect_dbt", "cli"),
    "DbtCoreOperation": ("prefect_dbt", "cli"),
    "SnowflakeTargetConfigs": ("prefect_dbt", "cli.configs.snowflake"),
    "BigQueryTargetConfigs": ("prefect_dbt", "cli.configs.bigquery"),
    "PostgresTargetConfigs": ("prefect_dbt", "cli.configs.postgres"),
}

# Declare API for type-checkers
__all__ = [
    "__version__",
    "PrefectDbtSettings",
    "PrefectDbtRunner",
    "DbtCloudCredentials",
    "DbtCloudJob",
]


def __getattr__(attr_name: str):
    if attr_name in _public_api:
        package, module = _public_api[attr_name]
        try:
            import importlib

            mod = importlib.import_module(f".{module}", package=package)
            result = getattr(mod, attr_name)
            return result
        except ImportError:
            if "configs" in module:  # For the database-specific configs
                return None
            raise
    raise AttributeError(f"module '{__name__}' has no attribute '{attr_name}'")


__version__ = _version.__version__
