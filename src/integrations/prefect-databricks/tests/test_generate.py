import sys
from pathlib import Path

import pytest
import yaml

TEST_DIR = Path(__file__).resolve().parent
try:
    from prefect_collection_generator.rest import populate_collection_repo
except ImportError:
    populate_collection_repo = None


@pytest.mark.skipif(
    condition=populate_collection_repo is None,
    reason="prefect-collection-generator is not public yet; cannot run on CI",
)
class TestPreprocessFn:
    @pytest.fixture()
    def processed_schema(self):
        sys.path.append(str(TEST_DIR / ".." / "scripts"))
        from generate import preprocess_fn  # noqa

        path = TEST_DIR / "mock_schema.yaml"
        with open(path, "r") as f:
            mock_schema = yaml.safe_load(f)

        processed_schema = preprocess_fn(mock_schema)
        return processed_schema

    def test_node_type_id(self, processed_schema):
        new_cluster = processed_schema["components"]["schemas"]["NewCluster"]
        node_type_id = new_cluster["properties"]["node_type_id"]
        node_type_id_description = node_type_id["description"]
        # description should be updated
        assert node_type_id_description.endswith("`instance_pool_id` is specified.")
        # node_type_id should be deleted from required
        assert new_cluster["required"] == ["spark_version"]

    def test_force_required_into_list(self, processed_schema):
        new_cluster = processed_schema["components"]["schemas"]["GitSource"]
        git_provider = new_cluster["properties"]["git_provider"]
        assert git_provider["required"] == [True]

    def test_items_to_have_type(self, processed_schema):
        new_cluster = processed_schema["components"]["schemas"]["GitSource"]
        totally_made_up = new_cluster["properties"]["totally_made_up"]
        assert totally_made_up["items"] == {"type": "imagination"}
