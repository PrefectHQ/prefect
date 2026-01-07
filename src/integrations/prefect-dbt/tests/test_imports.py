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
    from prefect_dbt import DbtCliProfile  # noqa: PLC0415

    assert DbtCliProfile is not None


def test_lazy_import_global_configs():
    """Test that GlobalConfigs can be lazily imported."""
    from prefect_dbt import GlobalConfigs  # noqa: PLC0415

    assert GlobalConfigs is not None


def test_lazy_import_target_configs():
    """Test that TargetConfigs can be lazily imported."""
    from prefect_dbt import TargetConfigs  # noqa: PLC0415

    assert TargetConfigs is not None


def test_lazy_import_database_configs():
    """Test that database-specific configs can be lazily imported."""
    from prefect_dbt import (  # noqa: PLC0415
        BigQueryTargetConfigs,
        PostgresTargetConfigs,
        SnowflakeTargetConfigs,
    )

    assert PostgresTargetConfigs is not None
    assert BigQueryTargetConfigs is not None
    assert SnowflakeTargetConfigs is not None


def test_invalid_attribute():
    """Test that accessing an invalid attribute raises ImportError."""
    with pytest.raises(ImportError) as exc_info:
        from prefect_dbt import NonExistentAttribute  # noqa: F401, PLC0415

    assert "cannot import name 'NonExistentAttribute' from 'prefect_dbt'" in str(
        exc_info.value
    )


def test_all_exports():
    """Test that __all__ contains expected exports."""
    import prefect_dbt  # noqa: PLC0415

    assert hasattr(prefect_dbt, "__version__")
    assert hasattr(prefect_dbt, "PrefectDbtSettings")
    assert hasattr(prefect_dbt, "PrefectDbtRunner")
    assert hasattr(prefect_dbt, "DbtCloudCredentials")
    assert hasattr(prefect_dbt, "DbtCloudJob")
