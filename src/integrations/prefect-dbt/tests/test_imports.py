import pytest
from prefect_dbt import (
    DbtCloudCredentials,
    DbtCloudJob,
    PrefectDbtSettings,
)


def test_direct_imports():
    """Test that directly imported objects are available."""
    assert PrefectDbtSettings is not None
    assert DbtCloudCredentials is not None
    assert DbtCloudJob is not None


def test_lazy_import_dbt_cli_profile():
    """Test that DbtCliProfile can be lazily imported."""
    from prefect_dbt import DbtCliProfile

    assert DbtCliProfile is not None


def test_lazy_import_global_configs():
    """Test that GlobalConfigs can be lazily imported."""
    from prefect_dbt import GlobalConfigs

    assert GlobalConfigs is not None


def test_lazy_import_target_configs():
    """Test that TargetConfigs can be lazily imported."""
    from prefect_dbt import TargetConfigs

    assert TargetConfigs is not None


def test_lazy_import_database_configs():
    """Test that database-specific configs can be lazily imported."""
    from prefect_dbt import (
        BigQueryTargetConfigs,
        PostgresTargetConfigs,
        SnowflakeTargetConfigs,
    )

    assert PostgresTargetConfigs is not None
    assert BigQueryTargetConfigs is not None
    assert SnowflakeTargetConfigs is not None


def test_invalid_attribute():
    """Test that accessing an invalid attribute raises AttributeError."""
    with pytest.raises(AttributeError) as exc_info:
        pass

    assert "module 'prefect_dbt' has no attribute 'NonExistentAttribute'" in str(
        exc_info.value
    )


def test_all_exports():
    """Test that __all__ contains expected exports."""
    import prefect_dbt

    assert hasattr(prefect_dbt, "__version__")
    assert hasattr(prefect_dbt, "PrefectDbtSettings")
    assert hasattr(prefect_dbt, "PrefectDbtRunner")
    assert hasattr(prefect_dbt, "DbtCloudCredentials")
    assert hasattr(prefect_dbt, "DbtCloudJob")
