import json
from uuid import uuid4

from prefect.client.orchestration import PrefectClient
from prefect.filesystems import LocalFileSystem
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


async def test_result_storage_cli_e2e(
    enable_ephemeral_server,
    prefect_client: PrefectClient,
    tmp_path,
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        ["result-storage", "inspect"],
        expected_code=0,
        expected_output_contains="No default result storage is configured.",
    )

    await run_sync_in_worker_thread(
        invoke_and_assert,
        ["result-storage", "inspect", "--output", "yaml"],
        expected_code=1,
        expected_output_contains="Only 'json' output format is supported.",
    )

    await run_sync_in_worker_thread(
        invoke_and_assert,
        ["result-storage", "set", "server-default-results"],
        expected_code=1,
        expected_output_contains=(
            "'server-default-results' is not valid. Slug must contain a '/'"
        ),
    )

    block_name = f"server-default-results-{uuid4()}"
    block_document_id = await LocalFileSystem(basepath=str(tmp_path)).asave(
        block_name,
        client=prefect_client,
    )

    try:
        await run_sync_in_worker_thread(
            invoke_and_assert,
            ["result-storage", "set", f"local-file-system/{block_name}"],
            expected_code=0,
            expected_output_contains="Set default result storage.",
        )

        configuration = await prefect_client.read_server_default_result_storage()
        assert configuration.default_result_storage_block_id == block_document_id

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            ["result-storage", "inspect", "--output", "json"],
            expected_code=0,
        )
        assert json.loads(result.stdout.strip()) == {
            "default_result_storage_block_id": str(block_document_id),
            "block": f"local-file-system/{block_name}",
        }

        await run_sync_in_worker_thread(
            invoke_and_assert,
            ["result-storage", "clear"],
            expected_code=0,
            expected_output_contains="Cleared default result storage.",
        )

        configuration = await prefect_client.read_server_default_result_storage()
        assert configuration.default_result_storage_block_id is None

        await run_sync_in_worker_thread(
            invoke_and_assert,
            ["result-storage", "set", "--id", str(block_document_id)],
            expected_code=0,
            expected_output_contains="Set default result storage.",
        )

        configuration = await prefect_client.read_server_default_result_storage()
        assert configuration.default_result_storage_block_id == block_document_id
    finally:
        await prefect_client.clear_server_default_result_storage()
