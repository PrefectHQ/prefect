# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license

import asyncio

import prefect
import pytest
from asynctest import CoroutineMock
from prefect.engine.result import NoResult, Result, SafeResult
from prefect.engine.result_handlers import JSONResultHandler
from prefect.engine.state import Failed, Retrying, Running, Submitted, Success

from prefect_server import api
from prefect_server.database import models
from prefect_server.utilities.exceptions import Unauthenticated, Unauthorized


class TestSetFlowRunStates:
    mutation = """
        mutation($input: set_flow_run_states_input!) {
            set_flow_run_states(input: $input) {
                states {
                    id
                    status
                    message
                }
            }
        }
    """

    async def test_set_flow_run_state(self, run_query, flow_run_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            flow_run_id=flow_run_id,
                            version=1,
                            state=Running().serialize(),
                        )
                    ]
                )
            ),
        )

        assert result.data.set_flow_run_states.states[0].status == "SUCCESS"
        assert result.data.set_flow_run_states.states[0].message is None

        fr = await models.FlowRun.where(
            id=result.data.set_flow_run_states.states[0].id
        ).first({"state", "version"})
        assert fr.version == 2
        assert fr.state == "Running"

    @pytest.mark.parametrize(
        "payload_response",
        [
            {"status": "SUCCESS"},
            {"status": "QUEUED"},
            {"status": "a status we don't actually use"},
        ],
    )
    async def test_returns_status_from_underlying_call(
        self, run_query, flow_run_id, payload_response, monkeypatch
    ):
        """
        This test should ensure that the `status` field should be determined
        based on the underlying `api.states.set_flow_run_state()` call. 
        """

        mock_state_api = CoroutineMock(return_value=payload_response)

        monkeypatch.setattr(
            "src.prefect_server.graphql.states.api.states.set_flow_run_state",
            mock_state_api,
        )

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            flow_run_id=flow_run_id,
                            version=1,
                            state=Running().serialize(),
                        )
                    ]
                )
            ),
        )

        mock_state_api.assert_awaited_once()

        assert (
            result.data.set_flow_run_states.states[0].status
            == payload_response["status"]
        )

    async def test_sets_flow_run_to_queued_if_no_slots_available(
        self, run_query, labeled_flow_id, flow_concurrency_limit
    ):

        run_1 = await api.runs.create_flow_run(labeled_flow_id)

        to_be_queued = await asyncio.gather(
            *[api.runs.create_flow_run(labeled_flow_id) for _ in range(10)]
        )

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(flow_run_id=run_1, version=1, state=Running().serialize(),)
                    ]
                )
            ),
        )
        # Should succeed since slots are available
        assert result.data.set_flow_run_states.states[0].status == "SUCCESS"

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(flow_run_id=run_id, version=1, state=Running().serialize())
                        for run_id in to_be_queued
                    ]
                )
            ),
        )
        # Should fail due to concurrency check
        for payload in result.data.set_flow_run_states.states:
            assert payload.status == "QUEUED"

        num_running_runs = await models.FlowRun.where(
            {"state": {"_eq": "Running"}}
        ).count()
        num_queued_runs = await models.FlowRun.where(
            {"state": {"_eq": "Queued"}}
        ).count()

        assert num_running_runs == 1
        assert num_queued_runs == len(to_be_queued)

    async def test_set_multiple_flow_run_states(
        self, run_query, flow_run_id, flow_run_id_2, flow_run_id_3
    ):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            flow_run_id=flow_run_id,
                            version=1,
                            state=Running().serialize(),
                        ),
                        dict(
                            flow_run_id=flow_run_id_2,
                            version=10,
                            state=Success().serialize(),
                        ),
                        dict(
                            flow_run_id=flow_run_id_3,
                            version=3,
                            state=Retrying().serialize(),
                        ),
                    ]
                )
            ),
        )
        assert result.data.set_flow_run_states.states == [
            {"id": flow_run_id, "status": "SUCCESS", "message": None},
            {"id": flow_run_id_2, "status": "SUCCESS", "message": None},
            {"id": flow_run_id_3, "status": "SUCCESS", "message": None},
        ]

        fr1 = await models.FlowRun.where(
            id=result.data.set_flow_run_states.states[0].id
        ).first({"state", "version"})
        assert fr1.version == 2
        assert fr1.state == "Running"

        fr2 = await models.FlowRun.where(
            id=result.data.set_flow_run_states.states[1].id
        ).first({"state", "version"})
        assert fr2.version == 3
        assert fr2.state == "Success"

        fr3 = await models.FlowRun.where(
            id=result.data.set_flow_run_states.states[2].id
        ).first({"state", "version"})
        assert fr3.version == 4
        assert fr3.state == "Retrying"

    async def test_set_multiple_flow_run_states_with_error(
        self, run_query, flow_run_id, flow_run_id_2, flow_run_id_3
    ):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            flow_run_id=flow_run_id,
                            version=1,
                            state=Running().serialize(),
                        ),
                        dict(
                            flow_run_id=flow_run_id_2, version=10, state="a bad state",
                        ),
                        dict(
                            flow_run_id=flow_run_id_3,
                            version=3,
                            state=Retrying().serialize(),
                        ),
                    ]
                )
            ),
        )
        assert result.data.set_flow_run_states is None
        assert result.errors[0].message

    async def test_set_flow_run_state_with_result(self, run_query, flow_run_id):
        result = Result(10, result_handler=JSONResultHandler())
        result.store_safe_value()
        state = Success(result=result)

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            flow_run_id=flow_run_id, version=0, state=state.serialize()
                        )
                    ]
                )
            ),
        )
        fr = await models.FlowRun.where(
            id=result.data.set_flow_run_states.states[0].id
        ).first({"state", "version"})
        assert fr.version == 2
        assert fr.state == "Success"

    async def test_set_flow_run_state_with_saferesult(self, run_query, flow_run_id):
        result = SafeResult("10", result_handler=JSONResultHandler())
        state = Success(result=result)

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            flow_run_id=flow_run_id, version=0, state=state.serialize()
                        )
                    ]
                )
            ),
        )
        fr = await models.FlowRun.where(
            id=result.data.set_flow_run_states.states[0].id
        ).first({"state", "version"})
        assert fr.version == 2
        assert fr.state == "Success"


# ---------------------------------------------------------------
# Task runs
# ---------------------------------------------------------------


class TestSetTaskRunStates:
    mutation = """
        mutation($input: set_task_run_states_input!) {
            set_task_run_states(input: $input) {
                states {
                    id
                    status
                    message
                }
            }
        }
    """

    async def test_set_multiple_task_run_states(
        self, run_query, running_flow_run_id, task_run_id, task_run_id_2, task_run_id_3
    ):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            task_run_id=task_run_id,
                            version=0,
                            state=Running().serialize(),
                        ),
                        dict(
                            task_run_id=task_run_id_2,
                            version=10,
                            state=Success().serialize(),
                        ),
                        dict(
                            task_run_id=task_run_id_3,
                            version=1,
                            state=Retrying().serialize(),
                        ),
                    ]
                )
            ),
        )
        assert result.data.set_task_run_states.states == [
            {"id": task_run_id, "status": "SUCCESS", "message": None},
            {"id": task_run_id_2, "status": "SUCCESS", "message": None},
            {"id": task_run_id_3, "status": "SUCCESS", "message": None},
        ]

        tr1 = await models.TaskRun.where(
            id=result.data.set_task_run_states.states[0].id
        ).first({"state", "version"})
        assert tr1.version == 1
        assert tr1.state == "Running"

        tr2 = await models.TaskRun.where(
            id=result.data.set_task_run_states.states[1].id
        ).first({"state", "version"})
        assert tr2.version == 2
        assert tr2.state == "Success"

        tr3 = await models.TaskRun.where(
            id=result.data.set_task_run_states.states[2].id
        ).first({"state", "version"})
        assert tr3.version == 2
        assert tr3.state == "Retrying"

    @pytest.mark.parametrize(
        "payload_response",
        [
            {"status": "SUCCESS"},
            {"status": "QUEUED"},
            {"status": "a status we don't actually use"},
        ],
    )
    async def test_returns_status_from_underlying_call(
        self, run_query, task_run_id, payload_response, monkeypatch
    ):
        """
        This test should ensure that the `status` field should be determined
        based on the underlying `api.states.set_flow_run_state()` call. 
        """

        mock_state_api = CoroutineMock(return_value=payload_response)

        monkeypatch.setattr(
            "src.prefect_server.graphql.states.api.states.set_task_run_state",
            mock_state_api,
        )

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            task_run_id=task_run_id,
                            version=0,
                            state=Running().serialize(),
                        )
                    ]
                )
            ),
        )

        mock_state_api.assert_awaited_once()

        assert (
            result.data.set_task_run_states.states[0].status
            == payload_response["status"]
        )

    async def test_set_multiple_task_run_states(
        self, run_query, running_flow_run_id, task_run_id, task_run_id_2, task_run_id_3
    ):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            task_run_id=task_run_id,
                            version=0,
                            state=Running().serialize(),
                        ),
                        dict(
                            task_run_id=task_run_id_2, version=10, state="a bad state",
                        ),
                        dict(
                            task_run_id=task_run_id_3,
                            version=1,
                            state=Retrying().serialize(),
                        ),
                    ]
                )
            ),
        )
        assert result.data.set_task_run_states is None
        assert result.errors[0].message

    async def test_set_task_run_state_with_result(self, run_query, task_run_id):
        result = Result(10, result_handler=JSONResultHandler())
        result.store_safe_value()
        state = Success(result=result)

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            task_run_id=task_run_id, version=0, state=state.serialize()
                        )
                    ]
                )
            ),
        )
        tr = await models.TaskRun.where(
            id=result.data.set_task_run_states.states[0].id
        ).first({"state", "version"})
        assert tr.version == 1
        assert tr.state == "Success"

    async def test_set_task_run_state_with_safe_result(self, run_query, task_run_id):
        result = SafeResult("10", result_handler=JSONResultHandler())
        state = Success(result=result)

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            task_run_id=task_run_id, version=0, state=state.serialize()
                        )
                    ]
                )
            ),
        )
        tr = await models.TaskRun.where(
            id=result.data.set_task_run_states.states[0].id
        ).first({"state", "version"})
        assert tr.version == 1
        assert tr.state == "Success"

    async def test_set_task_run_state(
        self, run_query, running_flow_run_id, task_run_id
    ):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            task_run_id=task_run_id,
                            version=0,
                            state=Running().serialize(),
                        )
                    ]
                )
            ),
        )
        tr = await models.TaskRun.where(
            id=result.data.set_task_run_states.states[0].id
        ).first({"state", "version"})
        assert tr.version == 1
        assert tr.state == "Running"

    async def test_set_task_run_state_with_correct_flow_run_version(
        self, run_query, flow_run_id, task_run_id
    ):
        await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=Running())

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            task_run_id=task_run_id,
                            version=0,
                            state=Running().serialize(),
                            flow_run_version=2,
                        )
                    ]
                )
            ),
        )
        tr = await models.TaskRun.where(
            id=result.data.set_task_run_states.states[0].id
        ).first({"state", "version"})
        assert tr.version == 1
        assert tr.state == "Running"
