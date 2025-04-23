from uuid import uuid4

import numpy as np
import pytest
from pydantic import ValidationError

from prefect.server.schemas.actions import (
    BlockTypeUpdate,
    DeploymentCreate,
    DeploymentScheduleCreate,
    DeploymentScheduleUpdate,
    DeploymentUpdate,
    FlowRunCreate,
    WorkPoolCreate,
    WorkPoolUpdate,
)
from prefect.server.schemas.schedules import CronSchedule
from prefect.settings import PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS


@pytest.mark.parametrize(
    "test_params,expected_dict",
    [
        ({"param": 1}, {"param": 1}),
        ({"param": "1"}, {"param": "1"}),
        ({"param": {1: 2}}, {"param": {"1": 2}}),
        (
            {"df": {"col": {0: "1"}}},
            {"df": {"col": {"0": "1"}}},
        ),  # Example of serialized dataframe parameter with int key
        (
            {"df": {"col": {0: np.float64(1.0)}}},
            {"df": {"col": {"0": 1.0}}},
        ),  # Example of serialized dataframe parameter with numpy value
    ],
)
class TestFlowRunCreate:
    def test_model_dump_json_mode_succeeds_with_parameters(
        self, test_params, expected_dict
    ):
        frc = FlowRunCreate(flow_id=uuid4(), flow_version="0.1", parameters=test_params)
        res = frc.model_dump(mode="json")
        assert res["parameters"] == expected_dict


class TestDeploymentCreate:
    def test_create_with_worker_pool_queue_id_warns(self):
        with pytest.warns(
            UserWarning,
            match=(
                "`worker_pool_queue_id` is no longer supported for creating or updating "
                "deployments. Please use `work_pool_name` and "
                "`work_queue_name` instead."
            ),
        ):
            deployment_create = DeploymentCreate(
                **dict(
                    name="test-deployment",
                    flow_id=uuid4(),
                    worker_pool_queue_id=uuid4(),
                )
            )

        assert getattr(deployment_create, "worker_pool_queue_id", 0) == 0

    @pytest.mark.parametrize(
        "kwargs",
        [
            ({"worker_pool_queue_name": "test-worker-pool-queue"}),
            ({"work_pool_queue_name": "test-work-pool-queue"}),
            ({"worker_pool_name": "test-worker-pool"}),
        ],
    )
    def test_create_with_worker_pool_name_warns(self, kwargs):
        with pytest.warns(
            UserWarning,
            match=(
                "`worker_pool_name`, `worker_pool_queue_name`, and "
                "`work_pool_name` are"
                "no longer supported for creating or updating "
                "deployments. Please use `work_pool_name` and "
                "`work_queue_name` instead."
            ),
        ):
            deployment_create = DeploymentCreate(
                **dict(name="test-deployment", flow_id=uuid4(), **kwargs)
            )

        for key in kwargs.keys():
            assert getattr(deployment_create, key, 0) == 0

    def test_check_valid_configuration_ignores_required_fields(self):
        """
        Deployment actions ignore required fields because we don't know
        what the final set of job variables will look like until a flow runs.
        """
        deployment_create = DeploymentCreate(
            name="test-deployment",
            flow_id=uuid4(),
            job_variables={},
        )

        base_job_template = {
            "variables": {
                "type": "object",
                "required": ["my-field"],
                "properties": {
                    "my-field": {
                        "type": "string",
                        "title": "My Field",
                    },
                },
            }
        }
        # This should pass despite my-field being required
        deployment_create.check_valid_configuration(base_job_template)

        # A field with a default value should also pass
        base_job_template = {
            "variables": {
                "type": "object",
                "required": ["my-field"],
                "properties": {
                    "my-field": {
                        "type": "string",
                        "title": "My Field",
                        "default": "my-default-for-my-field",
                    },
                },
            }
        }
        deployment_create.check_valid_configuration(base_job_template)

        # make sure the required fields are still there
        assert "my-field" in base_job_template["variables"]["required"]

        # This should also pass
        base_job_template = {
            "variables": {
                "type": "object",
                "required": ["my-field"],
                "properties": {
                    "my-field": {
                        "type": "string",
                        "title": "My Field",
                        "default": "my-default-for-my-field",
                    },
                },
            }
        }
        deployment_create = DeploymentUpdate(
            job_variables={"my_field": "my_value"},
        )
        deployment_create.check_valid_configuration(base_job_template)

    def test_validate_concurrency_limits_raises_with_both_limits(self):
        """Test that validation fails when both concurrency_limit and global_concurrency_limit_id are set"""
        # Test validation fails when both limits are provided
        with pytest.raises(
            ValueError,
            match="A deployment cannot have both a concurrency limit and a global concurrency limit.",
        ):
            DeploymentCreate(
                name="test-deployment",
                flow_id=uuid4(),
                concurrency_limit=5,
                global_concurrency_limit_id=uuid4(),
            )

        # Test validation passes with just concurrency_limit
        deployment = DeploymentCreate(
            name="test-deployment", flow_id=uuid4(), concurrency_limit=5
        )
        assert deployment.concurrency_limit == 5
        assert deployment.global_concurrency_limit_id is None

        # Test validation passes with just global_concurrency_limit_id
        global_limit_id = uuid4()
        deployment = DeploymentCreate(
            name="test-deployment",
            flow_id=uuid4(),
            global_concurrency_limit_id=global_limit_id,
        )
        assert deployment.global_concurrency_limit_id == global_limit_id
        assert deployment.concurrency_limit is None

        # Test validation passes with neither limit
        deployment = DeploymentCreate(name="test-deployment", flow_id=uuid4())
        assert deployment.concurrency_limit is None
        assert deployment.global_concurrency_limit_id is None


class TestDeploymentUpdate:
    def test_update_with_worker_pool_queue_id_warns(self):
        with pytest.warns(
            UserWarning,
            match=(
                "`worker_pool_queue_id` is no longer supported for creating or updating "
                "deployments. Please use `work_pool_name` and "
                "`work_queue_name` instead."
            ),
        ):
            deployment_update = DeploymentUpdate(**dict(worker_pool_queue_id=uuid4()))

        assert getattr(deployment_update, "worker_pool_queue_id", 0) == 0

    @pytest.mark.parametrize(
        "kwargs",
        [
            ({"worker_pool_queue_name": "test-worker-pool-queue"}),
            ({"work_pool_queue_name": "test-work-pool-queue"}),
            ({"worker_pool_name": "test-worker-pool"}),
        ],
    )
    def test_update_with_worker_pool_name_warns(self, kwargs):
        with pytest.warns(
            UserWarning,
            match=(
                "`worker_pool_name`, `worker_pool_queue_name`, and "
                "`work_pool_name` are"
                "no longer supported for creating or updating "
                "deployments. Please use `work_pool_name` and "
                "`work_queue_name` instead."
            ),
        ):
            deployment_update = DeploymentCreate(
                name="test-deployment", flow_id=uuid4(), **kwargs
            )

        for key in kwargs.keys():
            assert getattr(deployment_update, key, 0) == 0

    def test_check_valid_configuration_ignores_required_fields(self):
        """
        Deployment actions ignore required fields because we don't know
        what the final set of job variables will look like until a flow runs.
        """
        deployment_update = DeploymentUpdate(
            job_variables={},
        )

        base_job_template = {
            "variables": {
                "type": "object",
                "required": ["my-field"],
                "properties": {
                    "my-field": {
                        "type": "string",
                        "title": "My Field",
                    },
                },
            }
        }
        # This should pass even though my-field is required
        deployment_update.check_valid_configuration(base_job_template)

        # This should pass because the value has a default
        base_job_template = {
            "variables": {
                "type": "object",
                "required": ["my-field"],
                "properties": {
                    "my-field": {
                        "type": "string",
                        "title": "My Field",
                        "default": "my-default-for-my-field",
                    },
                },
            }
        }
        deployment_update.check_valid_configuration(base_job_template)

        # make sure the required fields are still there
        assert "my-field" in base_job_template["variables"]["required"]

        # This should also pass
        base_job_template = {
            "variables": {
                "type": "object",
                "required": ["my-field"],
                "properties": {
                    "my-field": {
                        "type": "string",
                        "title": "My Field",
                        "default": "my-default-for-my-field",
                    },
                },
            }
        }
        deployment_update = DeploymentUpdate(
            job_variables={"my_field": "my_value"},
        )
        deployment_update.check_valid_configuration(base_job_template)


def test_validate_concurrency_limits_raises_with_both_limits():
    """Test that validation fails when both concurrency_limit and global_concurrency_limit_id are set"""
    # Test validation fails when both limits are provided
    with pytest.raises(
        ValueError,
        match="A deployment cannot have both a concurrency limit and a global concurrency limit.",
    ):
        DeploymentUpdate(
            concurrency_limit=5,
            global_concurrency_limit_id=uuid4(),
        )

    # Test validation passes with just concurrency_limit
    deployment = DeploymentUpdate(concurrency_limit=5)
    assert deployment.concurrency_limit == 5
    assert deployment.global_concurrency_limit_id is None

    # Test validation passes with just global_concurrency_limit_id
    global_limit_id = uuid4()
    deployment = DeploymentUpdate(global_concurrency_limit_id=global_limit_id)
    assert deployment.global_concurrency_limit_id == global_limit_id
    assert deployment.concurrency_limit is None

    # Test validation passes with neither limit
    deployment = DeploymentUpdate()
    assert deployment.concurrency_limit is None
    assert deployment.global_concurrency_limit_id is None


class TestBlockTypeUpdate:
    def test_updatable_fields(self):
        fields = BlockTypeUpdate.updatable_fields()
        assert fields == {
            "logo_url",
            "documentation_url",
            "description",
            "code_example",
        }


class TestWorkPoolCreate:
    @pytest.mark.parametrize(
        "template",
        [
            {
                "job_configuration": {"thing_one": "{{ expected_variable }}"},
                "variables": {
                    "properties": {"wrong_variable": {}},
                    "required": [],
                },
            },
            {
                "job_configuration": {
                    "thing_one": "{{ expected_variable_1 }}",
                    "thing_two": "{{ expected_variable_2 }}",
                },
                "variables": {
                    "properties": {
                        "not_expected_variable_1": {},
                        "expected_variable_2": {},
                    },
                    "required": [],
                },
            },
        ],
    )
    async def test_validate_base_job_template_fails(self, template):
        """Test that error is raised if base_job_template job_configuration
        expects a variable that is not provided in variables."""
        with pytest.raises(
            ValueError,
            match=(
                r"Your job configuration uses the following undeclared variable\(s\):"
                r" expected_variable"
            ),
        ):
            WorkPoolCreate(name="test", base_job_template=template)

    @pytest.mark.parametrize(
        "template",
        [
            dict(),
            {
                "job_configuration": {"thing_one": "{{ expected_variable }}"},
                "variables": {
                    "properties": {"expected_variable": {}},
                    "required": [],
                },
            },
        ],
    )
    async def test_validate_base_job_template_succeeds(self, template):
        """Test that no error is raised if all variables expected by job_configuration
        are provided in variables."""
        wp = WorkPoolCreate(name="test", type="test", base_job_template=template)
        assert wp


class TestWorkPoolUpdate:
    @pytest.mark.parametrize(
        "template",
        [
            {
                "job_configuration": {"thing_one": "{{ expected_variable }}"},
                "variables": {
                    "properties": {"wrong_variable": {}},
                    "required": [],
                },
            },
            {
                "job_configuration": {
                    "thing_one": "{{ expected_variable_1 }}",
                    "thing_two": "{{ expected_variable_2 }}",
                },
                "variables": {
                    "properties": {
                        "not_expected_variable_1": {},
                        "expected_variable_2": {},
                    },
                    "required": [],
                },
            },
        ],
    )
    async def test_validate_base_job_template_fails(self, template):
        """Test that error is raised if base_job_template job_configuration
        expects a variable that is not provided in variables."""
        with pytest.raises(
            ValueError,
            match=(
                r"Your job configuration uses the following undeclared variable\(s\):"
                r" expected_variable"
            ),
        ):
            WorkPoolUpdate(base_job_template=template)

    @pytest.mark.parametrize(
        "template",
        [
            dict(),
            {
                "job_configuration": {"thing_one": "{{ expected_variable }}"},
                "variables": {
                    "properties": {"expected_variable": {}},
                    "required": [],
                },
            },
        ],
    )
    async def test_validate_base_job_template_succeeds(self, template):
        """Test that no error is raised if all variables expected by job_configuration
        are provided in variables."""
        wp = WorkPoolUpdate(base_job_template=template)
        assert wp


class TestDeploymentScheduleValidation:
    @pytest.mark.parametrize(
        "schema_type",
        [DeploymentScheduleCreate, DeploymentScheduleUpdate],
    )
    @pytest.mark.parametrize(
        "max_scheduled_runs,expected_error_substr",
        [
            (
                420000,
                f"be less than or equal to {PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS.value()}",
            ),
        ],
    )
    def test_deployment_schedule_validation_error(
        self, schema_type, max_scheduled_runs, expected_error_substr
    ):
        with pytest.raises(ValueError, match=expected_error_substr):
            schema_type(
                schedule=CronSchedule(cron="0 0 * * *"),
                max_scheduled_runs=max_scheduled_runs,
            )

    @pytest.mark.parametrize(
        "schema_type",
        [DeploymentScheduleCreate, DeploymentScheduleUpdate],
    )
    @pytest.mark.parametrize(
        "max_scheduled_runs",
        [-1, 0],
    )
    def test_deployment_schedule_validation_error_invalid_max_scheduled_runs(
        self, schema_type, max_scheduled_runs
    ):
        with pytest.raises(ValidationError):
            schema_type(
                schedule=CronSchedule(cron="0 0 * * *"),
                max_scheduled_runs=max_scheduled_runs,
            )

    @pytest.mark.parametrize(
        "schema_type",
        [DeploymentScheduleCreate, DeploymentScheduleUpdate],
    )
    @pytest.mark.parametrize(
        "max_scheduled_runs",
        [1, PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS.value()],
    )
    def test_deployment_schedule_validation_success(
        self, schema_type, max_scheduled_runs
    ):
        schedule = schema_type(
            schedule=CronSchedule(cron="0 0 * * *"),
            max_scheduled_runs=max_scheduled_runs,
        )
        assert schedule.max_scheduled_runs == max_scheduled_runs
