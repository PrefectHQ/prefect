from __future__ import annotations

from uuid import uuid4

import pytest

from prefect._internal.context import _EnvironmentRunContext


class TestEnvironmentRunContext:
    def test_context_get_outside_context_is_none(self):
        assert _EnvironmentRunContext.get() is None

    def test_context_enter_and_exit(self):
        flow_run_id = uuid4()
        ctx = _EnvironmentRunContext(flow_run_id=flow_run_id)

        assert _EnvironmentRunContext.get() is None

        with ctx:
            assert _EnvironmentRunContext.get() is ctx
            assert _EnvironmentRunContext.get().flow_run_id == flow_run_id

        assert _EnvironmentRunContext.get() is None

    def test_context_nesting(self):
        flow_run_id_1 = uuid4()
        flow_run_id_2 = uuid4()

        with _EnvironmentRunContext(flow_run_id=flow_run_id_1):
            assert _EnvironmentRunContext.get().flow_run_id == flow_run_id_1

            with _EnvironmentRunContext(flow_run_id=flow_run_id_2):
                assert _EnvironmentRunContext.get().flow_run_id == flow_run_id_2

            assert _EnvironmentRunContext.get().flow_run_id == flow_run_id_1

        assert _EnvironmentRunContext.get() is None

    def test_single_context_cannot_be_entered_multiple_times(self):
        ctx = _EnvironmentRunContext(flow_run_id=uuid4())
        with ctx:
            with pytest.raises(RuntimeError, match="Context already entered"):
                with ctx:
                    pass

    def test_copied_context_can_be_reentered(self):
        flow_run_id = uuid4()
        ctx = _EnvironmentRunContext(flow_run_id=flow_run_id)
        with ctx:
            with ctx.model_copy():
                assert _EnvironmentRunContext.get().flow_run_id == flow_run_id

    def test_from_environment_returns_none_without_flow_run_id(self, monkeypatch):
        monkeypatch.delenv("PREFECT__FLOW_RUN_ID", raising=False)
        assert _EnvironmentRunContext.from_environment() is None

    def test_from_environment_with_flow_run_id_only(self, monkeypatch):
        flow_run_id = uuid4()
        monkeypatch.setenv("PREFECT__FLOW_RUN_ID", str(flow_run_id))
        monkeypatch.delenv("PREFECT__DEPLOYMENT_ID", raising=False)
        monkeypatch.delenv("PREFECT__WORK_POOL_NAME", raising=False)

        ctx = _EnvironmentRunContext.from_environment()
        assert ctx is not None
        assert ctx.flow_run_id == flow_run_id
        assert ctx.deployment_id is None
        assert ctx.work_pool_name is None

    def test_from_environment_with_all_fields(self, monkeypatch):
        flow_run_id = uuid4()
        deployment_id = uuid4()
        work_pool_name = "test-pool"

        monkeypatch.setenv("PREFECT__FLOW_RUN_ID", str(flow_run_id))
        monkeypatch.setenv("PREFECT__DEPLOYMENT_ID", str(deployment_id))
        monkeypatch.setenv("PREFECT__WORK_POOL_NAME", work_pool_name)

        ctx = _EnvironmentRunContext.from_environment()
        assert ctx is not None
        assert ctx.flow_run_id == flow_run_id
        assert ctx.deployment_id == deployment_id
        assert ctx.work_pool_name == work_pool_name

    def test_from_environment_with_partial_fields(self, monkeypatch):
        flow_run_id = uuid4()
        deployment_id = uuid4()

        monkeypatch.setenv("PREFECT__FLOW_RUN_ID", str(flow_run_id))
        monkeypatch.setenv("PREFECT__DEPLOYMENT_ID", str(deployment_id))
        monkeypatch.delenv("PREFECT__WORK_POOL_NAME", raising=False)

        ctx = _EnvironmentRunContext.from_environment()
        assert ctx is not None
        assert ctx.flow_run_id == flow_run_id
        assert ctx.deployment_id == deployment_id
        assert ctx.work_pool_name is None

    def test_get_logger_returns_adapter_with_flow_run_id(self):
        flow_run_id = uuid4()
        ctx = _EnvironmentRunContext(flow_run_id=flow_run_id)

        logger = ctx.get_logger("test.logger")

        assert logger.extra["flow_run_id"] == str(flow_run_id)

    def test_get_logger_includes_deployment_context(self):
        flow_run_id = uuid4()
        deployment_id = uuid4()
        work_pool_name = "test-pool"

        ctx = _EnvironmentRunContext(
            flow_run_id=flow_run_id,
            deployment_id=deployment_id,
            work_pool_name=work_pool_name,
        )

        logger = ctx.get_logger("test.logger")

        assert logger.extra["flow_run_id"] == str(flow_run_id)
        assert logger.extra["deployment_id"] == str(deployment_id)
        assert logger.extra["work_pool_name"] == work_pool_name

    def test_get_logger_omits_none_fields(self):
        flow_run_id = uuid4()
        ctx = _EnvironmentRunContext(flow_run_id=flow_run_id)

        logger = ctx.get_logger("test.logger")

        assert "flow_run_id" in logger.extra
        assert "deployment_id" not in logger.extra
        assert "work_pool_name" not in logger.extra

    def test_serialize_includes_all_fields(self):
        flow_run_id = uuid4()
        deployment_id = uuid4()
        work_pool_name = "test-pool"

        ctx = _EnvironmentRunContext(
            flow_run_id=flow_run_id,
            deployment_id=deployment_id,
            work_pool_name=work_pool_name,
        )

        serialized = ctx.serialize()

        assert serialized["flow_run_id"] == flow_run_id
        assert serialized["deployment_id"] == deployment_id
        assert serialized["work_pool_name"] == work_pool_name

    def test_from_environment_handles_invalid_uuid_gracefully(self, monkeypatch):
        monkeypatch.setenv("PREFECT__FLOW_RUN_ID", "not-a-uuid")

        with pytest.raises(ValueError):
            _EnvironmentRunContext.from_environment()
