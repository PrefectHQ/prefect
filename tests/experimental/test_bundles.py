import signal
from typing import Literal

import pytest

from prefect import flow
from prefect._experimental.bundles import (
    create_bundle_for_flow_run,
    execute_bundle_in_subprocess,
)
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import FlowFilter, FlowFilterName
from prefect.context import TagsContext
from prefect.exceptions import Abort


@pytest.mark.parametrize("engine_type", ["sync", "async"])
class TestExecuteBundleInSubprocess:
    async def get_flow_run_for_flow(
        self, prefect_client: PrefectClient, flow_name: str
    ):
        flow_runs = await prefect_client.read_flow_runs(
            flow_filter=FlowFilter(name=FlowFilterName(any_=[flow_name]))
        )
        assert len(flow_runs) == 1
        return flow_runs[0]

    async def test_basic(
        self, prefect_client: PrefectClient, engine_type: Literal["sync", "async"]
    ):
        if engine_type == "sync":

            @flow(
                name="TestExecuteBundleInSubprocess.test_basic[sync]",
                persist_result=True,
            )
            def simple_flow():
                return "I'm a simple flow, and as a simple flow I believe in speaking plainly."
        else:

            @flow(
                name="TestExecuteBundleInSubprocess.test_basic[async]",
                persist_result=True,
            )
            async def simple_flow():
                return "I'm a simple flow, and as a simple flow I believe in speaking plainly."

        flow_run = await prefect_client.create_flow_run(
            flow=simple_flow,
        )

        bundle = create_bundle_for_flow_run(simple_flow, flow_run)
        process = execute_bundle_in_subprocess(bundle)

        process.join()
        assert process.exitcode == 0

        flow_run = await self.get_flow_run_for_flow(prefect_client, simple_flow.name)
        assert flow_run.state is not None
        assert flow_run.state.is_completed()
        assert (
            await flow_run.state.result()
            == "I'm a simple flow, and as a simple flow I believe in speaking plainly."
        )

    async def test_flow_ends_in_failed(
        self, prefect_client: PrefectClient, engine_type: Literal["sync", "async"]
    ):
        if engine_type == "sync":

            @flow(name="TestExecuteBundleInSubprocess.test_flow_ends_in_failed[sync]")
            def foo():
                raise ValueError("xyz")
        else:

            @flow(name="TestExecuteBundleInSubprocess.test_flow_ends_in_failed[async]")
            async def foo():
                raise ValueError("xyz")

        flow_run = await prefect_client.create_flow_run(flow=foo)

        bundle = create_bundle_for_flow_run(foo, flow_run)
        process = execute_bundle_in_subprocess(bundle)

        process.join()
        assert process.exitcode == 1

        flow_run = await self.get_flow_run_for_flow(prefect_client, foo.name)
        assert flow_run.state is not None
        assert flow_run.state.is_failed()

    async def test_with_parameters(
        self, prefect_client: PrefectClient, engine_type: Literal["sync", "async"]
    ):
        if engine_type == "sync":

            @flow(
                name="TestExecuteBundleInSubprocess.test_with_parameters[sync]",
                persist_result=True,
            )
            def flow_with_parameters(x: int, y: str):
                return f"x: {x}, y: {y}"
        else:

            @flow(
                name="TestExecuteBundleInSubprocess.test_with_parameters[async]",
                persist_result=True,
            )
            async def flow_with_parameters(x: int, y: str):
                return f"x: {x}, y: {y}"

        flow_run = await prefect_client.create_flow_run(
            flow=flow_with_parameters,
            parameters={"x": 42, "y": "hello"},
        )

        bundle = create_bundle_for_flow_run(flow_with_parameters, flow_run)
        process = execute_bundle_in_subprocess(bundle)

        process.join()
        assert process.exitcode == 0

        flow_run = await self.get_flow_run_for_flow(
            prefect_client, flow_with_parameters.name
        )
        assert flow_run.state is not None
        assert flow_run.state.is_completed()
        assert await flow_run.state.result() == "x: 42, y: hello"

    async def test_with_provided_context(
        self, prefect_client: PrefectClient, engine_type: Literal["sync", "async"]
    ):
        if engine_type == "sync":

            @flow(
                name="TestExecuteBundleInSubprocess.test_with_provided_context[sync]",
                persist_result=True,
            )
            def context_flow():
                return TagsContext.get().current_tags
        else:

            @flow(
                name="TestExecuteBundleInSubprocess.test_with_provided_context[async]",
                persist_result=True,
            )
            async def context_flow():
                return TagsContext.get().current_tags

        context = {"tags_context": TagsContext(current_tags={"foo", "bar"}).serialize()}

        flow_run = await prefect_client.create_flow_run(
            flow=context_flow,
        )

        bundle = create_bundle_for_flow_run(
            flow=context_flow, flow_run=flow_run, context=context
        )
        process = execute_bundle_in_subprocess(bundle)
        process.join()
        assert process.exitcode == 0

        flow_run = await self.get_flow_run_for_flow(prefect_client, context_flow.name)
        assert flow_run.state is not None
        assert flow_run.state.is_completed()
        assert await flow_run.state.result() == {"foo", "bar"}

    async def test_flow_is_aborted(
        self, engine_type: Literal["sync", "async"], prefect_client: PrefectClient
    ):
        if engine_type == "sync":

            @flow(
                name="TestExecuteBundleInSubprocess.test_flow_is_aborted[sync]",
                persist_result=True,
            )
            def foo():
                raise Abort()
        else:

            @flow(
                name="TestExecuteBundleInSubprocess.test_flow_is_aborted[async]",
                persist_result=True,
            )
            async def foo():
                raise Abort()

        flow_run = await prefect_client.create_flow_run(flow=foo)

        bundle = create_bundle_for_flow_run(foo, flow_run)
        process = execute_bundle_in_subprocess(bundle)
        process.join()
        assert process.exitcode == 0

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        # Stays in running state because the flow run is aborted manually
        assert flow_run.state is not None
        assert flow_run.state.is_running()

    async def test_flow_raises_a_base_exception(
        self, prefect_client: PrefectClient, engine_type: Literal["sync", "async"]
    ):
        if engine_type == "sync":

            @flow(
                name="TestExecuteBundleInSubprocess.test_flow_raises_a_base_exception[sync]",
                persist_result=True,
            )
            def foo():
                raise BaseException()
        else:

            @flow(
                name="TestExecuteBundleInSubprocess.test_flow_raises_a_base_exception[async]",
                persist_result=True,
            )
            async def foo():
                raise BaseException()

        flow_run = await prefect_client.create_flow_run(flow=foo)

        bundle = create_bundle_for_flow_run(foo, flow_run)
        process = execute_bundle_in_subprocess(bundle)
        process.join()
        assert process.exitcode == 1

        flow_run = await self.get_flow_run_for_flow(prefect_client, foo.name)
        assert flow_run.state is not None
        assert flow_run.state.is_crashed()

    async def test_flow_process_is_killed(
        self, prefect_client: PrefectClient, engine_type: Literal["sync", "async"]
    ):
        if engine_type == "sync":

            @flow(
                name="TestExecuteBundleInSubprocess.test_flow_process_is_killed[sync]",
                persist_result=True,
            )
            def foo():
                signal.raise_signal(signal.SIGKILL)
        else:

            @flow(
                name="TestExecuteBundleInSubprocess.test_flow_process_is_killed[async]",
                persist_result=True,
            )
            async def foo():
                signal.raise_signal(signal.SIGKILL)

        flow_run = await prefect_client.create_flow_run(flow=foo)

        bundle = create_bundle_for_flow_run(foo, flow_run)
        process = execute_bundle_in_subprocess(bundle)
        process.join()
        assert process.exitcode == -9

        flow_run = await self.get_flow_run_for_flow(prefect_client, foo.name)
        # Stays in running state because the process died
        assert flow_run.state is not None
        assert flow_run.state.is_running()
