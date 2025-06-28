import uuid

import pytest

import prefect.exceptions
from prefect import flow
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


async def read_queue(prefect_client, name, pool=None):
    return await prefect_client.read_work_queue_by_name(name=name, work_pool_name=pool)


class TestCreateWorkQueue:
    def test_create_work_queue(self):
        invoke_and_assert(
            command="work-queue create q-name",
            expected_output_contains=[
                "Created work queue with properties:",
                "name - 'q-name'",
            ],
            expected_code=0,
        )

    def test_create_work_queue_with_limit(self):
        invoke_and_assert(
            command="work-queue create q-name -l 3",
            expected_output_contains=[
                "Created work queue with properties:",
                "concurrency limit - 3",
            ],
            expected_code=0,
        )

    async def test_create_work_queue_with_pool(
        self,
        prefect_client,
        work_pool,
    ):
        queue_name = "q-name"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue create {queue_name} -p {work_pool.name}",
            expected_code=0,
        )

        queue = await read_queue(
            prefect_client,
            name=queue_name,
            pool=work_pool.name,
        )
        assert queue.work_pool_id == work_pool.id
        assert queue.name == queue_name

    async def test_create_work_queue_with_priority(
        self,
        prefect_client,
        work_pool,
    ):
        queue_name = "q-name"
        queue_priority = 1
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"work-queue create {queue_name} -p {work_pool.name} -q"
                f" {queue_priority}"
            ),
            expected_code=0,
        )

        queue = await read_queue(
            prefect_client,
            name=queue_name,
            pool=work_pool.name,
        )
        assert queue.work_pool_id == work_pool.id
        assert queue.name == queue_name
        assert queue.priority == queue_priority

    async def test_create_work_queue_without_pool_uses_default_pool(
        self, prefect_client
    ):
        queue_name = "q-name"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue create {queue_name}",
            expected_code=0,
        )

        queue = await read_queue(
            prefect_client,
            name=queue_name,
        )
        assert queue.name == queue_name
        assert queue.work_pool_id is not None

    def test_create_work_queue_with_bad_pool_name(
        self,
        prefect_client,
    ):
        queue_name = "q-name"
        invoke_and_assert(
            command=f"work-queue create {queue_name} -p bad-pool",
            expected_code=1,
        )
        assert "Work pool with name: 'bad-pool' not found."


class TestSetConcurrencyLimit:
    async def test_set_concurrency_limit(self, prefect_client, work_queue):
        assert work_queue.concurrency_limit is None
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue set-concurrency-limit {work_queue.name} 5",
            expected_code=0,
        )
        q = await read_queue(prefect_client, work_queue.name)
        assert q.concurrency_limit == 5

    async def test_set_concurrency_limit_by_id(self, prefect_client, work_queue):
        assert work_queue.concurrency_limit is None
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue set-concurrency-limit {work_queue.id} 5",
            expected_code=0,
        )
        q = await read_queue(prefect_client, work_queue.name)
        assert q.concurrency_limit == 5

    async def test_set_concurrency_limit_with_pool_with_name(
        self,
        prefect_client,
        work_queue_1,
    ):
        assert work_queue_1.concurrency_limit is None
        cmd = (
            f"work-queue set-concurrency-limit {work_queue_1.name} 5 "
            f"-p {work_queue_1.work_pool.name}"
        )
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=cmd,
            expected_code=0,
        )
        q = await read_queue(
            prefect_client, work_queue_1.name, pool=work_queue_1.work_pool.name
        )
        assert q.concurrency_limit == 5

    # Tests for all of the above, but with bad inputs
    def test_set_concurrency_limit_bad_queue_name(self):
        invoke_and_assert(
            command="work-queue set-concurrency-limit bad-name 5",
            expected_code=1,
        )

    def test_set_concurrency_limit_bad_queue_id(self):
        invoke_and_assert(
            command=(
                "work-queue set-concurrency-limit"
                " 00000000-0000-0000-0000-000000000000 5"
            ),
            expected_code=1,
        )

    def test_set_concurrency_limit_bad_pool_name(
        self,
        work_queue,
    ):
        invoke_and_assert(
            command=f"work-queue set-concurrency-limit {work_queue.name} 5 -p bad-pool",
            expected_code=1,
        )


class TestClearConcurrencyLimit:
    async def test_clear_concurrency_limit(self, prefect_client, work_queue):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue set-concurrency-limit {work_queue.name} 5",
        )
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue clear-concurrency-limit {work_queue.name}",
            expected_code=0,
        )
        q = await read_queue(prefect_client, work_queue.name)
        assert q.concurrency_limit is None

    async def test_clear_concurrency_limit_by_id(self, prefect_client, work_queue):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue set-concurrency-limit {work_queue.name} 5",
        )
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue clear-concurrency-limit {work_queue.id}",
            expected_code=0,
        )

        q = await read_queue(prefect_client, work_queue.name)
        assert q.concurrency_limit is None

    async def test_clear_concurrency_limit_with_pool(
        self,
        prefect_client,
        work_queue_1,
    ):
        pool_name = work_queue_1.work_pool.name

        await prefect_client.update_work_queue(id=work_queue_1.id, concurrency_limit=5)

        work_pool_queue = await read_queue(
            prefect_client,
            name=work_queue_1.name,
            pool=pool_name,
        )
        assert work_pool_queue.concurrency_limit == 5

        cmd = (
            f"work-queue clear-concurrency-limit {work_pool_queue.name} -p {pool_name}"
        )
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=cmd,
            expected_code=0,
        )
        q = await read_queue(prefect_client, work_queue_1.name, pool=pool_name)
        assert q.concurrency_limit is None

    # Tests for all of the above, but with bad inputs
    def test_clear_concurrency_limit_bad_queue_name(self):
        invoke_and_assert(
            command="work-queue clear-concurrency-limit bad-name",
            expected_code=1,
        )

    def test_clear_concurrency_limit_bad_queue_id(self):
        invoke_and_assert(
            command=(
                "work-queue clear-concurrency-limit"
                " 00000000-0000-0000-0000-000000000000"
            ),
            expected_code=1,
        )

    def test_clear_concurrency_limit_bad_pool_name(
        self,
        work_queue,
    ):
        invoke_and_assert(
            command=f"work-queue clear-concurrency-limit {work_queue.name} -p bad-pool",
            expected_code=1,
        )


class TestPauseWorkQueue:
    async def test_pause(self, prefect_client, work_queue):
        assert not work_queue.is_paused
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue pause {work_queue.name} --pool default-agent-pool",
            expected_code=0,
        )
        q = await read_queue(prefect_client, work_queue.name)
        assert q.is_paused

    async def test_pause_by_id(self, prefect_client, work_queue):
        assert not work_queue.is_paused
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue pause {work_queue.id} --pool default-agent-pool",
            expected_code=0,
        )
        q = await read_queue(prefect_client, work_queue.name)
        assert q.is_paused

    async def test_pause_with_pool(
        self,
        prefect_client,
        work_queue_1,
    ):
        assert not work_queue_1.is_paused
        cmd = f"work-queue pause {work_queue_1.name} -p {work_queue_1.work_pool.name}"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=cmd,
            expected_code=0,
        )
        q = await read_queue(
            prefect_client,
            name=work_queue_1.name,
            pool=work_queue_1.work_pool.name,
        )
        assert q.is_paused

    # Tests for all of the above, but with bad inputs
    def test_pause_bad_queue_name(self):
        invoke_and_assert(
            command="work-queue pause bad-name",
            expected_code=1,
        )

    def test_pause_bad_queue_id(self):
        invoke_and_assert(
            command="work-queue pause 00000000-0000-0000-0000-000000000000",
            expected_code=1,
        )

    def test_pause_bad_pool_name(
        self,
        work_queue,
    ):
        invoke_and_assert(
            command=f"work-queue pause {work_queue.name} -p bad-pool",
            expected_code=1,
        )

    def test_pause_without_specifying_pool_name_without_confirmation(
        self,
        work_queue,
    ):
        invoke_and_assert(
            command=f"work-queue pause {work_queue.name}",
            expected_code=1,
        )

    async def test_pause_without_specifying_pool_name_with_confirmation(
        self,
        prefect_client,
        work_queue,
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue pause {work_queue.name}",
            user_input="Y",
            expected_code=0,
        )
        q = await read_queue(prefect_client, work_queue.name)
        assert q.is_paused

    async def test_pause_without_specifying_pool_name_with_abort(
        self,
        prefect_client,
        work_queue,
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue pause {work_queue.name}",
            user_input="N",
            expected_code=1,
            expected_output_contains="Work queue pause aborted!",
        )
        q = await read_queue(prefect_client, work_queue.name)
        assert not q.is_paused


class TestResumeWorkQueue:
    async def test_resume(self, prefect_client, work_queue):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue pause {work_queue.name} --pool default-agent-pool",
        )
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue resume {work_queue.name}",
            expected_code=0,
        )
        q = await read_queue(prefect_client, work_queue.name)
        assert not q.is_paused

    async def test_resume_by_id(self, prefect_client, work_queue):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue pause {work_queue.name} --pool default-agent-pool",
        )
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue resume {work_queue.id}",
            expected_code=0,
        )
        q = await read_queue(prefect_client, work_queue.name)
        assert not q.is_paused

    async def test_resume_with_pool(
        self,
        prefect_client,
        work_queue_1,
    ):
        pool_name = work_queue_1.work_pool.name
        await prefect_client.update_work_queue(
            id=work_queue_1.id,
            is_paused=True,
        )

        work_pool_queue = await read_queue(
            prefect_client,
            name=work_queue_1.name,
            pool=pool_name,
        )
        assert work_pool_queue.is_paused

        cmd = f"work-queue resume {work_queue_1.name} -p {pool_name}"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=cmd,
            expected_code=0,
        )
        q = await read_queue(prefect_client, work_queue_1.name, pool=pool_name)
        assert not q.is_paused

    # Tests for all of the above, but with bad inputs
    def test_resume_bad_queue_name(self):
        invoke_and_assert(
            command="work-queue resume bad-name",
            expected_code=1,
        )

    def test_resume_bad_queue_id(self):
        invoke_and_assert(
            command="work-queue resume 00000000-0000-0000-0000-000000000000",
            expected_code=1,
        )

    def test_resume_bad_pool_name(
        self,
        work_queue,
    ):
        invoke_and_assert(
            command=f"work-queue resume {work_queue.name} -p bad-pool",
            expected_code=1,
        )


class TestInspectWorkQueue:
    def test_inspect(self, work_queue):
        invoke_and_assert(
            command=f"work-queue inspect {work_queue.name}",
            expected_output_contains=[
                f"id='{work_queue.id}'",
                f"name={work_queue.name!r}",
            ],
            expected_code=0,
        )

    def test_inspect_by_id(self, work_queue):
        invoke_and_assert(
            command=f"work-queue inspect {work_queue.id}",
            expected_output_contains=[
                f"id='{work_queue.id}'",
                f"name={work_queue.name!r}",
            ],
            expected_code=0,
        )

    def test_inspect_with_pool(
        self,
        work_queue_1,
    ):
        cmd = f"work-queue inspect {work_queue_1.name} -p {work_queue_1.work_pool.name}"
        invoke_and_assert(
            command=cmd,
            expected_output_contains=[
                f"id='{work_queue_1.id}'",
                f"name={work_queue_1.name!r}",
            ],
            expected_code=0,
        )

    # Tests all of the above, but with bad input
    def test_inspect_bad_input_work_queue_name(self, work_queue):
        invoke_and_assert(
            command=f"work-queue inspect {work_queue.name}-bad",
            expected_code=1,
        )

    def test_inspect_bad_input_work_queue_id(self, work_queue):
        invoke_and_assert(
            command=f"work-queue inspect {work_queue.id}-bad",
            expected_code=1,
        )

    def test_inspect_bad_input_work_pool(
        self,
        work_queue_1,
    ):
        cmd = (
            f"work-queue inspect {work_queue_1.name} "
            f"-p {work_queue_1.work_pool.name}-bad"
        )
        invoke_and_assert(
            command=cmd,
            expected_code=1,
        )

    def test_inspect_with_json_output(self, work_queue):
        """Test work-queue inspect command with JSON output flag."""
        import json

        result = invoke_and_assert(
            command=f"work-queue inspect {work_queue.name} --output json",
            expected_code=0,
        )

        # Parse JSON output and verify it's valid JSON
        output_data = json.loads(result.stdout.strip())

        # Verify key fields are present
        assert "id" in output_data
        assert "name" in output_data
        assert "status_details" in output_data  # Combined status information
        assert output_data["id"] == str(work_queue.id)
        assert output_data["name"] == work_queue.name


class TestDelete:
    async def test_delete(self, prefect_client, work_queue):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue delete {work_queue.name}",
            user_input="y",
            expected_code=0,
        )
        with pytest.raises(prefect.exceptions.ObjectNotFound):
            await read_queue(prefect_client, work_queue.name)

    async def test_delete_by_id(self, prefect_client, work_queue):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue delete {work_queue.id}",
            user_input="y",
            expected_code=0,
        )
        with pytest.raises(prefect.exceptions.ObjectNotFound):
            await read_queue(prefect_client, work_queue.name)

    async def test_delete_with_pool(
        self,
        prefect_client,
        work_queue_1,
    ):
        pool_name = work_queue_1.work_pool.name
        cmd = f"work-queue delete {work_queue_1.name} -p {pool_name}"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=cmd,
            user_input="y",
            expected_code=0,
        )
        with pytest.raises(prefect.exceptions.ObjectNotFound):
            await read_queue(prefect_client, work_queue_1.name, pool=pool_name)

    # Tests all of the above, but with bad input
    async def test_delete_with_bad_pool(
        self,
        prefect_client,
        work_queue_1,
    ):
        pool_name = work_queue_1.work_pool.name
        cmd = f"work-queue delete {work_queue_1.name} -p {pool_name}bad"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=cmd,
            expected_code=1,
        )
        assert await read_queue(prefect_client, work_queue_1.name, pool=pool_name)

    async def test_delete_with_bad_queue_name(self, prefect_client, work_queue):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"work-queue delete {work_queue.name}bad",
            expected_code=1,
        )
        assert await read_queue(prefect_client, work_queue.name)


class TestPreview:
    def test_preview(self, work_queue):
        invoke_and_assert(
            command=f"work-queue preview {work_queue.name}",
            expected_code=0,
        )

    def test_preview_by_id(self, work_queue):
        invoke_and_assert(
            command=f"work-queue preview {work_queue.id}",
            expected_code=0,
        )

    def test_preview_with_pool(
        self,
        work_queue_1,
    ):
        cmd = f"work-queue preview {work_queue_1.name} -p {work_queue_1.work_pool.name}"
        invoke_and_assert(
            command=cmd,
            expected_code=0,
        )

    # Tests all of the above, but with bad input
    def test_preview_bad_queue(self, work_queue):
        invoke_and_assert(
            command=f"work-queue preview {work_queue.name}-bad",
            expected_code=1,
        )

    def test_preview_bad_id(self, work_queue):
        invoke_and_assert(
            command=f"work-queue preview {work_queue.id}-bad",
            expected_code=1,
        )

    def test_preview_bad_pool(
        self,
        work_queue_1,
    ):
        cmd = (
            f"work-queue preview {work_queue_1.name} "
            f"-p {work_queue_1.work_pool.name}-bad"
        )
        invoke_and_assert(
            command=cmd,
            expected_code=1,
        )


class TestLS:
    def test_ls(self, work_queue):
        invoke_and_assert(
            command="work-queue ls",
            expected_code=0,
        )

    def test_ls_with_pool(
        self,
        work_queue_1,
    ):
        cmd = f"work-queue ls -p {work_queue_1.work_pool.name}"
        invoke_and_assert(
            command=cmd,
            expected_code=0,
        )

    def test_ls_with_zero_concurrency_limit(
        self,
        work_queue_1,
    ):
        invoke_and_assert(
            command=f"work-queue set-concurrency-limit {work_queue_1.name} 0",
            expected_code=0,
        )
        invoke_and_assert(
            command="work-queue set-concurrency-limit default 0",
            expected_code=0,
        )
        invoke_and_assert(
            command=f"work-queue ls -p {work_queue_1.work_pool.name}",
            expected_code=0,
            expected_output_does_not_contain="None",
        )

    def test_ls_with_bad_pool(
        self,
        work_queue_1,
    ):
        cmd = f"work-queue ls -p {work_queue_1.work_pool.name}-bad"
        res = invoke_and_assert(
            command=cmd,
            expected_code=1,
        )
        assert f"No work pool found: '{work_queue_1.work_pool.name}-bad'" in res.output


class TestReadRuns:
    async def create_runs_in_queue(self, prefect_client, queue, count: int):
        foo = flow(lambda: None, name="foo")
        flow_id = await prefect_client.create_flow(foo)
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="test-deployment",
            work_queue_name=queue.name,
        )
        for _ in range(count):
            await prefect_client.create_flow_run_from_deployment(deployment_id)

    async def test_read_wq(self, prefect_client, work_queue):
        n_runs = 3
        await self.create_runs_in_queue(prefect_client, work_queue, n_runs)
        cmd = f"work-queue read-runs {work_queue.name}"
        result = await run_sync_in_worker_thread(
            invoke_and_assert, command=cmd, expected_code=0
        )
        assert f"Read {n_runs} runs for work queue" in result.output

    async def test_read_wq_with_pool(self, prefect_client, work_queue):
        n_runs = 3
        await self.create_runs_in_queue(prefect_client, work_queue, n_runs)
        cmd = (
            f"work-queue read-runs --pool {work_queue.work_pool.name} {work_queue.name}"
        )
        result = await run_sync_in_worker_thread(
            invoke_and_assert, command=cmd, expected_code=0
        )
        assert f"Read {n_runs} runs for work queue" in result.output

    def test_read_missing_wq(self, work_queue):
        bad_name = str(uuid.uuid4())
        cmd = f"work-queue read-runs --pool {work_queue.work_pool.name} {bad_name}"
        result = invoke_and_assert(command=cmd, expected_code=1)
        assert f"No work queue found: '{bad_name}'" in result.output

    def test_read_wq_with_missing_pool(self, work_queue):
        bad_name = str(uuid.uuid4())
        cmd = f"work-queue read-runs --pool {bad_name} {work_queue.name}"
        result = invoke_and_assert(command=cmd, expected_code=1)
        assert (
            f"No work queue named '{work_queue.name}' found in work pool '{bad_name}'"
            in result.output
        )
