# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import os
import pendulum
import pytest

import prefect
from prefect.engine.result import NoResult, Result, SafeResult
from prefect.engine.result_handlers import JSONResultHandler
from prefect.engine.state import Failed, Retrying, Running, Success, Submitted
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
