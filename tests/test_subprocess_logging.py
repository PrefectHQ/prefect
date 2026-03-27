"""Tests for `with_context` — propagating Prefect context to subprocesses."""

import multiprocessing
from concurrent.futures import ProcessPoolExecutor

import pytest

from prefect import flow, task
from prefect.context import with_context
from prefect.exceptions import MissingContextError
from prefect.logging import get_run_logger

# ---------------------------------------------------------------------------
# Helper functions executed in child processes
# ---------------------------------------------------------------------------


def _log_and_return_ids(item: int) -> dict:
    """Worker that uses get_run_logger() and returns context IDs."""
    from prefect.context import FlowRunContext, TaskRunContext

    logger = get_run_logger()
    logger.info(f"Processing {item}")

    flow_ctx = FlowRunContext.get()
    task_ctx = TaskRunContext.get()
    return {
        "item": item,
        "flow_run_id": str(flow_ctx.flow_run.id)
        if flow_ctx and flow_ctx.flow_run
        else None,
        "task_run_id": str(task_ctx.task_run.id) if task_ctx else None,
    }


def _just_get_logger(_: object = None) -> str:
    """Worker that calls get_run_logger() and returns its name."""
    logger = get_run_logger()
    return logger.name


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWithContextPoolMap:
    """multiprocessing.Pool.map with with_context."""

    def test_get_run_logger_works_in_pool_worker(self):
        @task
        def my_task():
            wrapped = with_context(_just_get_logger)
            with multiprocessing.get_context("spawn").Pool(1) as pool:
                results = pool.map(wrapped, [1])
            return results

        @flow
        def my_flow():
            return my_task()

        results = my_flow()
        assert len(results) == 1
        assert isinstance(results[0], str)

    def test_correct_run_ids_in_pool_worker(self):
        @task
        def my_task():
            from prefect.context import FlowRunContext, TaskRunContext

            flow_ctx = FlowRunContext.get()
            task_ctx = TaskRunContext.get()
            parent_flow_run_id = (
                str(flow_ctx.flow_run.id) if flow_ctx and flow_ctx.flow_run else None
            )
            parent_task_run_id = str(task_ctx.task_run.id) if task_ctx else None

            wrapped = with_context(_log_and_return_ids)
            with multiprocessing.get_context("spawn").Pool(1) as pool:
                results = pool.map(wrapped, [1, 2])
            return results, parent_flow_run_id, parent_task_run_id

        @flow
        def my_flow():
            return my_task()

        results, parent_flow_id, parent_task_id = my_flow()
        assert len(results) == 2
        for r in results:
            assert r["flow_run_id"] == parent_flow_id
            assert r["task_run_id"] == parent_task_id


class TestWithContextProcess:
    """multiprocessing.Process with with_context."""

    def test_get_run_logger_works_in_process(self):
        @task
        def my_task():
            ctx = multiprocessing.get_context("spawn")
            q: multiprocessing.Queue = ctx.Queue()  # type: ignore[type-arg]

            wrapped = with_context(_target_with_queue)
            p = ctx.Process(target=wrapped, args=(q,))
            p.start()
            p.join(timeout=30)
            assert q.get_nowait() == "ok"

        @flow
        def my_flow():
            return my_task()

        my_flow()


def _target_with_queue(queue: multiprocessing.Queue) -> None:  # type: ignore[type-arg]
    """Process target that puts a value on a queue after using get_run_logger."""
    logger = get_run_logger()
    logger.info("hello from subprocess")
    queue.put("ok")


class TestWithContextProcessPoolExecutor:
    """concurrent.futures.ProcessPoolExecutor with with_context."""

    def test_get_run_logger_works_in_executor(self):
        @task
        def my_task():
            wrapped = with_context(_just_get_logger)
            ctx = multiprocessing.get_context("spawn")
            with ProcessPoolExecutor(max_workers=1, mp_context=ctx) as executor:
                future = executor.submit(wrapped)
                return future.result(timeout=30)

        @flow
        def my_flow():
            return my_task()

        result = my_flow()
        assert isinstance(result, str)


class TestWithContextOutsideRun:
    """with_context called outside a flow/task run should raise."""

    def test_raises_missing_context_error(self):
        """with_context still works outside a run — it serializes whatever
        context exists (which may be empty). The error only happens when
        the subprocess tries to call get_run_logger() without a run context."""
        wrapped = with_context(_just_get_logger)
        # The wrapper itself is created fine, but calling it in a subprocess
        # without run context will fail when get_run_logger is called.
        with pytest.raises(MissingContextError):
            wrapped()


class TestWithContextFlowOnly:
    """with_context inside a flow (no task) propagates flow context."""

    def test_flow_context_propagated(self):
        @flow
        def my_flow():
            from prefect.context import FlowRunContext

            flow_ctx = FlowRunContext.get()
            parent_flow_run_id = (
                str(flow_ctx.flow_run.id) if flow_ctx and flow_ctx.flow_run else None
            )

            wrapped = with_context(_log_and_return_ids)
            ctx = multiprocessing.get_context("spawn")
            with ProcessPoolExecutor(max_workers=1, mp_context=ctx) as executor:
                future = executor.submit(wrapped, 42)
                result = future.result(timeout=30)
            return result, parent_flow_run_id

        result, parent_flow_id = my_flow()
        assert result["flow_run_id"] == parent_flow_id
        assert result["task_run_id"] is None
