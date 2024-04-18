from prefect_azure.ml_datastore import (
    ml_get_datastore,
    ml_list_datastores,
    ml_register_datastore_blob_container,
    ml_upload_datastore,
)

from prefect import flow


def test_ml_list_datastores_flow(ml_credentials):
    @flow
    def ml_list_datastores_flow():
        results = ml_list_datastores(ml_credentials)
        return results

    results = ml_list_datastores_flow()
    assert results == ["a", "b"]


async def test_ml_get_datastore_flow(ml_credentials, datastore):
    @flow
    async def ml_get_datastore_flow():
        result = await ml_get_datastore(ml_credentials, datastore_name="datastore_name")
        return result

    result = await ml_get_datastore_flow()
    assert result.datastore_name == "datastore_name"


async def test_ml_get_datastore_flow_default(ml_credentials, datastore):
    @flow
    async def ml_get_datastore_flow():
        result = await ml_get_datastore(ml_credentials)
        return result

    result = await ml_get_datastore_flow()
    assert result.datastore_name == "default"


async def test_ml_upload_datastore_flow(ml_credentials, datastore, tmp_path):
    @flow
    async def ml_upload_datastore_flow():
        result = await ml_upload_datastore(
            str(tmp_path),
            ml_credentials,
            target_path="target_path",
            overwrite=True,
        )
        return result

    result = await ml_upload_datastore_flow()
    assert result["src_dir"] == str(tmp_path)
    assert result["target_path"] == "target_path"
    assert result["overwrite"]


async def test_ml_upload_datastore_flow_pathlib(ml_credentials, datastore, tmp_path):
    @flow
    async def ml_upload_datastore_flow():
        result = await ml_upload_datastore(
            tmp_path,
            ml_credentials,
            target_path="target_path",
            overwrite=True,
        )
        return result

    result = await ml_upload_datastore_flow()
    assert result["src_dir"] == str(tmp_path)
    assert result["target_path"] == "target_path"
    assert result["overwrite"]


async def test_ml_register_datastore_blob_container_flow(
    ml_credentials, blob_storage_credentials, datastore
):
    @flow
    async def ml_register_datastore_blob_container_flow():
        result = await ml_register_datastore_blob_container(
            "container_name",
            ml_credentials,
            blob_storage_credentials,
        )
        return result

    result = await ml_register_datastore_blob_container_flow()
    assert result == "registered"
