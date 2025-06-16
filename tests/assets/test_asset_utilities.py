import pytest

from prefect.assets import Asset, AssetProperties
from prefect.context import TaskAssetContext


@pytest.mark.parametrize(
    "invalid_key",
    [
        "invalid-key",
        "assets/my-asset",
        "/path/to/file",
        "no-protocol-prefix",
        "UPPERCASE://resource",
        "://missing-protocol",
    ],
)
def test_asset_invalid_uri(invalid_key):
    with pytest.raises(ValueError, match="Key must be a valid URI"):
        Asset(key=invalid_key)


def test_asset_as_resource():
    asset = Asset(key="s3://bucket/data")
    resource = TaskAssetContext.asset_as_resource(asset)
    assert resource["prefect.resource.id"] == "s3://bucket/data"


def test_asset_as_related():
    asset = Asset(key="postgres://prod/users")
    related = TaskAssetContext.asset_as_related(asset)
    assert related["prefect.resource.id"] == "postgres://prod/users"
    assert related["prefect.resource.role"] == "asset"


def test_asset_as_resource_with_no_properties():
    asset = Asset(key="s3://bucket/data")
    resource = TaskAssetContext.asset_as_resource(asset)

    assert resource == {"prefect.resource.id": "s3://bucket/data"}
    assert "prefect.resource.name" not in resource
    assert "prefect.asset.description" not in resource
    assert "prefect.asset.url" not in resource
    assert "prefect.asset.owners" not in resource


def test_asset_as_resource_with_partial_properties():
    asset = Asset(
        key="postgres://prod/users",
        properties=AssetProperties(name="Users Table", description="Main users table"),
    )
    resource = TaskAssetContext.asset_as_resource(asset)

    expected = {
        "prefect.resource.id": "postgres://prod/users",
        "prefect.resource.name": "Users Table",
        "prefect.asset.description": "Main users table",
    }
    assert resource == expected
    assert "prefect.asset.url" not in resource
    assert "prefect.asset.owners" not in resource


def test_asset_as_resource_with_all_properties():
    asset = Asset(
        key="s3://data-lake/enriched/customers.parquet",
        properties=AssetProperties(
            name="Customer Data",
            description="Enriched customer dataset",
            url="https://dashboard.company.com/datasets/customers",
            owners=["data-team", "analytics"],
        ),
    )
    resource = TaskAssetContext.asset_as_resource(asset)

    expected = {
        "prefect.resource.id": "s3://data-lake/enriched/customers.parquet",
        "prefect.resource.name": "Customer Data",
        "prefect.asset.description": "Enriched customer dataset",
        "prefect.asset.url": "https://dashboard.company.com/datasets/customers",
        "prefect.asset.owners": '["data-team", "analytics"]',
    }
    assert resource == expected


def test_asset_as_resource_excludes_unset_properties():
    """Test that asset_as_resource excludes properties that were not explicitly set."""
    asset = Asset(
        key="postgres://prod/transactions",
        properties=AssetProperties(
            name="Transactions",
            # description is not set (will be None)
            # url is not set (will be None)
            owners=["finance-team"],
        ),
    )
    resource = TaskAssetContext.asset_as_resource(asset)

    # Should only include the fields that were explicitly set
    expected = {
        "prefect.resource.id": "postgres://prod/transactions",
        "prefect.resource.name": "Transactions",
        "prefect.asset.owners": '["finance-team"]',
    }
    assert resource == expected
    # Ensure unset fields are not included
    assert "prefect.asset.description" not in resource
    assert "prefect.asset.url" not in resource
