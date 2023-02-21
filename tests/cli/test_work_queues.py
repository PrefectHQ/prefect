import pytest

import prefect.exceptions
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread, sync_compatible


@sync_compatible
async def read_queue(orion_client, name, pool=None):
    return await orion_client.read_work_queue_by_name(name=name, work_pool_name=pool)


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

    @pytest.mark.filterwarnings("ignore::DeprecationWarning")
    def test_create_work_queue_with_tags(self):
        invoke_and_assert(
            command="work-queue create q-name -t blue -t red",
            expected_output_contains=[
                "Supplying `tags` for work queues is deprecated",
                "tags - blue, red",
            ],
            expected_code=0,
        )

    def test_create_work_queue_with_pool(
        self,
        orion_client,
        work_pool,
    ):
        queue_name = "q-name"
        res = invoke_and_assert(
            command=f"work-queue create {queue_name} -p {work_pool.name}",
            expected_code=0,
        )

        queue = read_queue(
            orion_client,
            name=queue_name,
            pool=work_pool.name,
        )
        assert queue.work_pool_id == work_pool.id
        assert queue.name == queue_name

    def test_work_queue_with_pool_and_tag_errors(
        self,
        work_pool,
    ):
        res = invoke_and_assert(
            command=f"work-queue create q-name -p {work_pool.name} -t dog",
            expected_code=1,
        )
        assert (
            "Work queues created with tags cannot specify work pools or set priorities."
            in res.output
        )

    def test_create_work_queue_without_pool_uses_default_pool(self, orion_client):
        queue_name = "q-name"
        res = invoke_and_assert(
            command=f"work-queue create {queue_name}",
            expected_code=0,
        )

        queue = read_queue(
            orion_client,
            name=queue_name,
        )
        assert queue.name == queue_name
        assert queue.work_pool_id is not None

    def test_create_work_queue_with_bad_pool_name(
        self,
        orion_client,
    ):
        queue_name = "q-name"
        res = invoke_and_assert(
            command=f"work-queue create {queue_name} -p bad-pool",
            expected_code=1,
        )
        assert f"Work pool with name: 'bad-pool' not found."


class TestSetConcurrencyLimit:
    def test_set_concurrency_limit(self, orion_client, work_queue):
        assert work_queue.concurrency_limit is None
        invoke_and_assert(
            command=f"work-queue set-concurrency-limit {work_queue.name} 5",
            expected_code=0,
        )
        q = read_queue(orion_client, work_queue.name)
        assert q.concurrency_limit == 5

    def test_set_concurrency_limit_by_id(self, orion_client, work_queue):
        assert work_queue.concurrency_limit is None
        invoke_and_assert(
            command=f"work-queue set-concurrency-limit {work_queue.id} 5",
            expected_code=0,
        )
        q = read_queue(orion_client, work_queue.name)
        assert q.concurrency_limit == 5

    def test_set_concurrency_limit_with_pool_with_name(
        self,
        orion_client,
        work_queue_1,
    ):
        assert work_queue_1.concurrency_limit is None
        cmd = (
            f"work-queue set-concurrency-limit {work_queue_1.name} 5 "
            f"-p {work_queue_1.work_pool.name}"
        )
        invoke_and_assert(
            command=cmd,
            expected_code=0,
        )
        q = read_queue(
            orion_client, work_queue_1.name, pool=work_queue_1.work_pool.name
        )
        assert q.concurrency_limit == 5

    # Tests for all of the above, but with bad inputs
    def test_set_concurrency_limit_bad_queue_name(self):
        invoke_and_assert(
            command=f"work-queue set-concurrency-limit bad-name 5",
            expected_code=1,
        )

    def test_set_concurrency_limit_bad_queue_id(self):
        invoke_and_assert(
            command=(
                f"work-queue set-concurrency-limit"
                f" 00000000-0000-0000-0000-000000000000 5"
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
    def test_clear_concurrency_limit(self, orion_client, work_queue):
        invoke_and_assert(
            command=f"work-queue set-concurrency-limit {work_queue.name} 5"
        )
        invoke_and_assert(
            command=f"work-queue clear-concurrency-limit {work_queue.name}",
            expected_code=0,
        )
        q = read_queue(orion_client, work_queue.name)
        assert q.concurrency_limit is None

    def test_clear_concurrency_limit_by_id(self, orion_client, work_queue):
        invoke_and_assert(
            command=f"work-queue set-concurrency-limit {work_queue.name} 5"
        )
        invoke_and_assert(
            command=f"work-queue clear-concurrency-limit {work_queue.id}",
            expected_code=0,
        )

        q = read_queue(orion_client, work_queue.name)
        assert q.concurrency_limit is None

    async def test_clear_concurrency_limit_with_pool(
        self,
        orion_client,
        work_queue_1,
    ):
        pool_name = work_queue_1.work_pool.name

        await orion_client.update_work_queue(id=work_queue_1.id, concurrency_limit=5)

        work_pool_queue = await read_queue(
            orion_client,
            name=work_queue_1.name,
            pool=pool_name,
        )
        assert work_pool_queue.concurrency_limit == 5

        cmd = (
            f"work-queue clear-concurrency-limit {work_pool_queue.name} -p {pool_name}"
        )
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=cmd,
            expected_code=0,
        )
        q = await read_queue(orion_client, work_queue_1.name, pool=pool_name)
        assert q.concurrency_limit is None

    # Tests for all of the above, but with bad inputs
    def test_clear_concurrency_limit_bad_queue_name(self):
        invoke_and_assert(
            command=f"work-queue clear-concurrency-limit bad-name",
            expected_code=1,
        )

    def test_clear_concurrency_limit_bad_queue_id(self):
        invoke_and_assert(
            command=(
                f"work-queue clear-concurrency-limit"
                f" 00000000-0000-0000-0000-000000000000"
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
    def test_pause(self, orion_client, work_queue):
        assert not work_queue.is_paused
        invoke_and_assert(
            command=f"work-queue pause {work_queue.name}",
            expected_code=0,
        )
        q = read_queue(orion_client, work_queue.name)
        assert q.is_paused

    def test_pause_by_id(self, orion_client, work_queue):
        assert not work_queue.is_paused
        invoke_and_assert(
            command=f"work-queue pause {work_queue.id}",
            expected_code=0,
        )
        q = read_queue(orion_client, work_queue.name)
        assert q.is_paused

    def test_pause_with_pool(
        self,
        orion_client,
        work_queue_1,
    ):
        assert not work_queue_1.is_paused
        cmd = f"work-queue pause {work_queue_1.name} -p {work_queue_1.work_pool.name}"
        invoke_and_assert(
            command=cmd,
            expected_code=0,
        )
        q = read_queue(
            orion_client,
            name=work_queue_1.name,
            pool=work_queue_1.work_pool.name,
        )
        assert q.is_paused

    # Tests for all of the above, but with bad inputs
    def test_pause_bad_queue_name(self):
        invoke_and_assert(
            command=f"work-queue pause bad-name",
            expected_code=1,
        )

    def test_pause_bad_queue_id(self):
        invoke_and_assert(
            command=f"work-queue pause 00000000-0000-0000-0000-000000000000",
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


class TestResumeWorkQueue:
    def test_resume(self, orion_client, work_queue):
        invoke_and_assert(command=f"work-queue pause {work_queue.name}")
        invoke_and_assert(
            command=f"work-queue resume {work_queue.name}",
            expected_code=0,
        )
        q = read_queue(orion_client, work_queue.name)
        assert not q.is_paused

    def test_resume_by_id(self, orion_client, work_queue):
        invoke_and_assert(command=f"work-queue pause {work_queue.name}")
        invoke_and_assert(
            command=f"work-queue resume {work_queue.id}",
            expected_code=0,
        )
        q = read_queue(orion_client, work_queue.name)
        assert not q.is_paused

    async def test_resume_with_pool(
        self,
        orion_client,
        work_queue_1,
    ):
        pool_name = work_queue_1.work_pool.name
        await orion_client.update_work_queue(
            id=work_queue_1.id,
            is_paused=True,
        )

        work_pool_queue = await read_queue(
            orion_client,
            name=work_queue_1.name,
            pool=pool_name,
        )
        assert work_pool_queue.is_paused

        cmd = f"work-queue resume {work_queue_1.name} -p {pool_name}"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=cmd,
            expected_code=0,
        )
        q = await read_queue(orion_client, work_queue_1.name, pool=pool_name)
        assert not q.is_paused

    # Tests for all of the above, but with bad inputs
    def test_resume_bad_queue_name(self):
        invoke_and_assert(
            command=f"work-queue resume bad-name",
            expected_code=1,
        )

    def test_resume_bad_queue_id(self):
        invoke_and_assert(
            command=f"work-queue resume 00000000-0000-0000-0000-000000000000",
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


class TestDelete:
    def test_delete(self, orion_client, work_queue):
        invoke_and_assert(
            command=f"work-queue delete {work_queue.name}",
            expected_code=0,
        )
        with pytest.raises(prefect.exceptions.ObjectNotFound):
            read_queue(orion_client, work_queue.name)

    def test_delete_by_id(self, orion_client, work_queue):
        invoke_and_assert(
            command=f"work-queue delete {work_queue.id}",
            expected_code=0,
        )
        with pytest.raises(prefect.exceptions.ObjectNotFound):
            read_queue(orion_client, work_queue.name)

    def test_delete_with_pool(
        self,
        orion_client,
        work_queue_1,
    ):
        pool_name = work_queue_1.work_pool.name
        cmd = f"work-queue delete {work_queue_1.name} -p {pool_name}"
        invoke_and_assert(
            command=cmd,
            expected_code=0,
        )
        with pytest.raises(prefect.exceptions.ObjectNotFound):
            read_queue(orion_client, work_queue_1.name, pool=pool_name)

    # Tests all of the above, but with bad input
    def test_delete_with_bad_pool(
        self,
        orion_client,
        work_queue_1,
    ):
        pool_name = work_queue_1.work_pool.name
        cmd = f"work-queue delete {work_queue_1.name} -p {pool_name}bad"
        invoke_and_assert(
            command=cmd,
            expected_code=1,
        )
        assert read_queue(orion_client, work_queue_1.name, pool=pool_name)

    def test_delete_with_bad_queue_name(self, orion_client, work_queue):
        invoke_and_assert(
            command=f"work-queue delete {work_queue.name}bad",
            expected_code=1,
        )
        assert read_queue(orion_client, work_queue.name)


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
