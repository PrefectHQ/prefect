import uuid

from prefect.blocks.system import Secret
from prefect.client.orchestration import PrefectClient
from prefect.filesystems import LocalFileSystem
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


async def test_server_result_storage_set_inspect_and_unset(
    prefect_client: PrefectClient, tmp_path
):
    block_name = f"server-default-{uuid.uuid4()}"
    block_document_id = await LocalFileSystem(basepath=tmp_path / "results").asave(
        name=block_name,
        client=prefect_client,
    )

    await run_sync_in_worker_thread(
        invoke_and_assert,
        ["server", "result-storage", "set", f"local-file-system/{block_name}"],
        expected_code=0,
        expected_output_contains=(
            f"Configured server default result storage to use 'local-file-system/{block_name}'."
        ),
    )

    configuration = await prefect_client.read_server_default_result_storage()
    assert configuration.default_result_storage_block_id == block_document_id

    await run_sync_in_worker_thread(
        invoke_and_assert,
        ["server", "result-storage", "inspect"],
        expected_code=0,
        expected_output_contains=[
            "Server Default Result Storage",
            str(block_document_id),
            f"local-file-system/{block_name}",
        ],
    )

    await run_sync_in_worker_thread(
        invoke_and_assert,
        ["server", "result-storage", "unset"],
        expected_code=0,
        expected_output_contains="Cleared the server default result storage configuration.",
    )

    configuration = await prefect_client.read_server_default_result_storage()
    assert configuration.default_result_storage_block_id is None


async def test_server_result_storage_set_rejects_non_storage_block(
    prefect_client: PrefectClient,
):
    block_name = f"not-storage-{uuid.uuid4()}"
    await Secret(value="super-secret").asave(
        name=block_name,
        client=prefect_client,
    )

    await run_sync_in_worker_thread(
        invoke_and_assert,
        ["server", "result-storage", "set", f"secret/{block_name}"],
        expected_code=1,
    )

    configuration = await prefect_client.read_server_default_result_storage()
    assert configuration.default_result_storage_block_id is None
