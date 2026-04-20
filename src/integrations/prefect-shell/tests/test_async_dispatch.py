"""Tests for async_dispatch migration in prefect-shell.

These tests verify the critical behavior from issue #15008 where
@sync_compatible would incorrectly return coroutines in sync context.
"""

import sys
from typing import Coroutine

import pytest
from prefect_shell.commands import ShellOperation, ShellProcess

from prefect import flow

if sys.platform == "win32":
    pytest.skip(reason="see test_commands_windows.py", allow_module_level=True)


class TestShellOperationTriggerAsyncDispatch:
    """Tests for ShellOperation.trigger migrated from @sync_compatible to @async_dispatch."""

    def test_trigger_sync_context_returns_process_not_coroutine(self):
        """trigger must return ShellProcess (not coroutine) in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """
        op = ShellOperation(commands=["echo 'test'"])

        @flow
        def test_flow():
            result = op.trigger()
            # The result inside the flow should be the actual value, not a coroutine
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        with op:
            process = test_flow()
            assert isinstance(process, ShellProcess)
            process.wait_for_completion()

    async def test_trigger_async_context_works(self):
        """trigger should work correctly in async context."""

        @flow
        async def test_flow():
            op = ShellOperation(commands=["echo 'test'"])
            async with op:
                # In async context, @async_dispatch dispatches to async version
                result = await op.atrigger()
                await result.await_for_completion()
                return result

        process = await test_flow()
        assert isinstance(process, ShellProcess)

    def test_atrigger_is_available(self):
        """atrigger should be available for direct async usage."""
        op = ShellOperation(commands=["echo 'test'"])
        assert hasattr(op, "atrigger")
        assert callable(op.atrigger)


class TestShellOperationRunAsyncDispatch:
    """Tests for ShellOperation.run migrated from @sync_compatible to @async_dispatch."""

    def test_run_sync_context_returns_value_not_coroutine(self):
        """run must return list (not coroutine) in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """
        op = ShellOperation(commands=["echo 'test output'"])

        @flow
        def test_flow():
            result = op.run()
            # The result should not be a coroutine
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert isinstance(result, list)
        assert "test output" in result

    async def test_run_async_context_works(self):
        """run should work correctly in async context."""

        @flow
        async def test_flow():
            op = ShellOperation(commands=["echo 'async test'"])
            # In async context, @async_dispatch dispatches to async version
            result = await op.arun()
            return result

        result = await test_flow()
        assert isinstance(result, list)
        assert "async test" in result

    def test_arun_is_available(self):
        """arun should be available for direct async usage."""
        op = ShellOperation(commands=["echo 'test'"])
        assert hasattr(op, "arun")
        assert callable(op.arun)


class TestShellProcessWaitForCompletionAsyncDispatch:
    """Tests for ShellProcess.wait_for_completion async_dispatch migration."""

    def test_wait_for_completion_sync_context_returns_none_not_coroutine(self):
        """wait_for_completion must not return coroutine in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """
        op = ShellOperation(commands=["echo 'test'"])

        @flow
        def test_flow():
            with op:
                process = op.trigger()
                result = process.wait_for_completion()
                # The result should not be a coroutine
                assert not isinstance(result, Coroutine), (
                    "sync context returned coroutine"
                )
                return process

        process = test_flow()
        assert isinstance(process, ShellProcess)

    def test_await_for_completion_is_available(self):
        """await_for_completion should be available for direct async usage."""
        op = ShellOperation(commands=["echo 'test'"])

        @flow
        def test_flow():
            with op:
                process = op.trigger()
                assert hasattr(process, "await_for_completion")
                assert callable(process.await_for_completion)
                process.wait_for_completion()

        test_flow()


class TestShellProcessFetchResultAsyncDispatch:
    """Tests for ShellProcess.fetch_result async_dispatch migration."""

    def test_fetch_result_sync_context_returns_value_not_coroutine(self):
        """fetch_result must return list (not coroutine) in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """
        op = ShellOperation(commands=["echo 'result test'"])

        @flow
        def test_flow():
            with op:
                process = op.trigger()
                process.wait_for_completion()
                result = process.fetch_result()
                # The result should not be a coroutine
                assert not isinstance(result, Coroutine), (
                    "sync context returned coroutine"
                )
                return result

        result = test_flow()
        assert isinstance(result, list)
        assert "result test" in result

    def test_afetch_result_is_available(self):
        """afetch_result should be available for direct async usage."""
        op = ShellOperation(commands=["echo 'test'"])

        @flow
        def test_flow():
            with op:
                process = op.trigger()
                process.wait_for_completion()
                assert hasattr(process, "afetch_result")
                assert callable(process.afetch_result)

        test_flow()


class TestShellOperationCloseAsyncDispatch:
    """Tests for ShellOperation.close async_dispatch migration."""

    def test_close_sync_context_returns_none_not_coroutine(self):
        """close must not return coroutine in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """
        op = ShellOperation(commands=["echo 'test'"])

        @flow
        def test_flow():
            result = op.close()
            # The result should not be a coroutine
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        test_flow()

    def test_aclose_is_available(self):
        """aclose should be available for direct async usage."""
        op = ShellOperation(commands=["echo 'test'"])
        assert hasattr(op, "aclose")
        assert callable(op.aclose)
