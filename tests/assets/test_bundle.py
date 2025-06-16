from prefect.assets.bundle import (
    BUNDLE_FORMAT_VERSION,
    decode_assets,
    encode_assets,
)
from prefect.assets.core import Asset, AssetProperties


class TestAssetBundle:
    def test_encode_decode_simple_assets(self):
        """Test basic encoding and decoding of assets with just keys."""
        assets = {
            Asset(key="s3://bucket/file1.parquet"),
            Asset(key="gs://bucket/file2.json"),
            Asset(key="file:///local/path/file3.csv"),
        }

        bundle = encode_assets(assets)

        assert isinstance(bundle, dict)
        assert bundle["format"] == "v1"
        assert "data" in bundle
        assert isinstance(bundle["data"], str)

        decoded_assets = decode_assets(bundle)

        assert len(decoded_assets) == len(assets)
        assert {asset.key for asset in decoded_assets} == {
            asset.key for asset in assets
        }

    def test_encode_decode_assets_with_properties(self):
        """Test encoding and decoding of assets with full properties."""
        assets = {
            Asset(
                key="s3://data/sales.parquet",
                properties=AssetProperties(
                    name="Sales Data",
                    description="Monthly sales metrics",
                    url="https://analytics.com/sales",
                    owners=["data-team", "sales@company.com"],
                ),
            ),
            Asset(
                key="gs://warehouse/users.json",
                properties=AssetProperties(name="User Data", owners=["eng-team"]),
            ),
            Asset(key="hdfs://cluster/logs.txt"),  # No properties
        }

        bundle = encode_assets(assets)
        decoded_assets = decode_assets(bundle)

        decoded_dict = {asset.key: asset for asset in decoded_assets}

        assert len(decoded_assets) == 3

        sales_asset = decoded_dict["s3://data/sales.parquet"]
        assert sales_asset.properties.name == "Sales Data"
        assert sales_asset.properties.description == "Monthly sales metrics"
        assert sales_asset.properties.url == "https://analytics.com/sales"
        assert sales_asset.properties.owners == ["data-team", "sales@company.com"]

        users_asset = decoded_dict["gs://warehouse/users.json"]
        assert users_asset.properties.name == "User Data"
        assert users_asset.properties.description is None
        assert users_asset.properties.url is None
        assert users_asset.properties.owners == ["eng-team"]

        logs_asset = decoded_dict["hdfs://cluster/logs.txt"]
        assert logs_asset.properties is None

    def test_encode_empty_set(self):
        """Test encoding an empty set of assets."""
        assets = set()
        bundle = encode_assets(assets)
        decoded = decode_assets(bundle)
        assert decoded == set()

    def test_decode_empty_bundle(self):
        """Test decoding various empty/invalid bundles."""
        assert decode_assets({}) == set()
        assert decode_assets(None) == set()
        assert decode_assets({"format": "v999", "data": "invalid"}) == set()

    def test_decode_invalid_data(self):
        """Test decoding with corrupted data."""
        bundle = {"format": BUNDLE_FORMAT_VERSION, "data": "not-valid-base64!!!"}
        decoded = decode_assets(bundle)
        assert decoded == set()

    def test_unsupported_format_version(self):
        """Test that unsupported format versions are silently handled."""
        bundle = {"format": "v999", "data": "some data"}
        decoded = decode_assets(bundle)
        assert decoded == set()

    def test_large_asset_set(self):
        """Test encoding and decoding a large set of assets."""
        assets = set()
        for i in range(1000):
            if i % 3 == 0:
                # Just key
                asset = Asset(key=f"s3://bucket/partition={i}/data.parquet")
            elif i % 3 == 1:
                # With name
                asset = Asset(
                    key=f"gs://warehouse/table_{i}/data.json",
                    properties=AssetProperties(name=f"Table {i}"),
                )
            else:
                # Full properties
                asset = Asset(
                    key=f"hdfs://cluster/path/{i}/output.csv",
                    properties=AssetProperties(
                        name=f"Dataset {i}",
                        description=f"Generated dataset number {i}",
                        url=f"https://data.com/{i}",
                        owners=[f"team{i % 5}"],
                    ),
                )
            assets.add(asset)

        bundle = encode_assets(assets)
        decoded = decode_assets(bundle)

        assert len(decoded) == 1000

        decoded_dict = {asset.key: asset for asset in decoded}

        assert decoded_dict["s3://bucket/partition=0/data.parquet"].properties is None

        assert (
            decoded_dict["gs://warehouse/table_1/data.json"].properties.name
            == "Table 1"
        )

        full_asset = decoded_dict["hdfs://cluster/path/2/output.csv"]
        assert full_asset.properties.name == "Dataset 2"
        assert full_asset.properties.description == "Generated dataset number 2"
        assert full_asset.properties.url == "https://data.com/2"
        assert full_asset.properties.owners == ["team2"]

    def test_properties_exclude_unset(self):
        """Test that unset properties are excluded from serialization."""
        asset = Asset(
            key="s3://bucket/data.parquet",
            properties=AssetProperties(
                name="My Data",
            ),
        )

        bundle = encode_assets({asset})
        decoded = decode_assets(bundle)

        decoded_asset = list(decoded)[0]
        assert decoded_asset.properties.name == "My Data"
        assert decoded_asset.properties.description is None
        assert decoded_asset.properties.url is None
        assert decoded_asset.properties.owners is None

        import base64
        import zlib

        import orjson

        decoded_data = orjson.loads(
            zlib.decompress(base64.b64decode(bundle["data"].encode()))
        )
        assert len(decoded_data) == 1
        assert decoded_data[0]["key"] == "s3://bucket/data.parquet"
        assert decoded_data[0]["properties"] == {"name": "My Data"}
