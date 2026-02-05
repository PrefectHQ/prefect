"""Tests for SDK generation data models."""

from prefect._sdk.models import (
    DeploymentInfo,
    FlowInfo,
    SDKData,
    SDKGenerationMetadata,
    WorkPoolInfo,
)


class TestWorkPoolInfo:
    """Test WorkPoolInfo data model."""

    def test_basic_creation(self):
        wp = WorkPoolInfo(
            name="my-pool",
            pool_type="kubernetes",
        )
        assert wp.name == "my-pool"
        assert wp.pool_type == "kubernetes"
        assert wp.job_variables_schema == {}

    def test_with_schema(self):
        schema = {
            "type": "object",
            "properties": {
                "image": {"type": "string"},
                "cpu": {"type": "string"},
            },
        }
        wp = WorkPoolInfo(
            name="k8s-pool",
            pool_type="kubernetes",
            job_variables_schema=schema,
        )
        assert wp.job_variables_schema == schema

    def test_different_types(self):
        docker = WorkPoolInfo(name="docker-pool", pool_type="docker")
        process = WorkPoolInfo(name="local-pool", pool_type="process")
        ecs = WorkPoolInfo(name="ecs-pool", pool_type="ecs")

        assert docker.pool_type == "docker"
        assert process.pool_type == "process"
        assert ecs.pool_type == "ecs"


class TestDeploymentInfo:
    """Test DeploymentInfo data model."""

    def test_basic_creation(self):
        dep = DeploymentInfo(
            name="production",
            flow_name="my-etl-flow",
            full_name="my-etl-flow/production",
        )
        assert dep.name == "production"
        assert dep.flow_name == "my-etl-flow"
        assert dep.full_name == "my-etl-flow/production"
        assert dep.parameter_schema is None
        assert dep.work_pool_name is None
        assert dep.description is None

    def test_with_all_fields(self):
        schema = {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "batch_size": {"type": "integer", "default": 100},
            },
            "required": ["source"],
        }
        dep = DeploymentInfo(
            name="production",
            flow_name="my-etl-flow",
            full_name="my-etl-flow/production",
            parameter_schema=schema,
            work_pool_name="k8s-pool",
            description="Production ETL deployment",
        )
        assert dep.parameter_schema == schema
        assert dep.work_pool_name == "k8s-pool"
        assert dep.description == "Production ETL deployment"

    def test_empty_parameter_schema(self):
        dep = DeploymentInfo(
            name="simple",
            flow_name="simple-flow",
            full_name="simple-flow/simple",
            parameter_schema={},
        )
        assert dep.parameter_schema == {}


class TestFlowInfo:
    """Test FlowInfo data model."""

    def test_basic_creation(self):
        flow = FlowInfo(name="my-flow")
        assert flow.name == "my-flow"
        assert flow.deployments == []

    def test_with_deployments(self):
        dep1 = DeploymentInfo(
            name="production",
            flow_name="my-flow",
            full_name="my-flow/production",
        )
        dep2 = DeploymentInfo(
            name="staging",
            flow_name="my-flow",
            full_name="my-flow/staging",
        )
        flow = FlowInfo(name="my-flow", deployments=[dep1, dep2])

        assert len(flow.deployments) == 2
        assert flow.deployments[0].name == "production"
        assert flow.deployments[1].name == "staging"


class TestSDKGenerationMetadata:
    """Test SDKGenerationMetadata data model."""

    def test_basic_creation(self):
        meta = SDKGenerationMetadata(
            generation_time="2026-01-06T14:30:00Z",
            prefect_version="3.2.0",
        )
        assert meta.generation_time == "2026-01-06T14:30:00Z"
        assert meta.prefect_version == "3.2.0"
        assert meta.workspace_name is None
        assert meta.api_url is None

    def test_with_all_fields(self):
        meta = SDKGenerationMetadata(
            generation_time="2026-01-06T14:30:00Z",
            prefect_version="3.2.0",
            workspace_name="my-workspace",
            api_url="https://api.prefect.cloud/api/accounts/xxx/workspaces/yyy",
        )
        assert meta.workspace_name == "my-workspace"
        assert (
            meta.api_url == "https://api.prefect.cloud/api/accounts/xxx/workspaces/yyy"
        )


class TestSDKData:
    """Test SDKData data model."""

    def test_basic_creation(self):
        meta = SDKGenerationMetadata(
            generation_time="2026-01-06T14:30:00Z",
            prefect_version="3.2.0",
        )
        data = SDKData(metadata=meta)

        assert data.metadata == meta
        assert data.flows == {}
        assert data.work_pools == {}
        assert data.deployment_names == []

    def test_counts_with_empty_data(self):
        meta = SDKGenerationMetadata(
            generation_time="2026-01-06T14:30:00Z",
            prefect_version="3.2.0",
        )
        data = SDKData(metadata=meta)

        assert data.flow_count == 0
        assert data.deployment_count == 0
        assert data.work_pool_count == 0

    def test_counts_with_data(self):
        meta = SDKGenerationMetadata(
            generation_time="2026-01-06T14:30:00Z",
            prefect_version="3.2.0",
        )

        dep1 = DeploymentInfo(
            name="production",
            flow_name="flow-a",
            full_name="flow-a/production",
        )
        dep2 = DeploymentInfo(
            name="staging",
            flow_name="flow-a",
            full_name="flow-a/staging",
        )
        dep3 = DeploymentInfo(
            name="daily",
            flow_name="flow-b",
            full_name="flow-b/daily",
        )

        flow_a = FlowInfo(name="flow-a", deployments=[dep1, dep2])
        flow_b = FlowInfo(name="flow-b", deployments=[dep3])

        wp = WorkPoolInfo(name="k8s-pool", pool_type="kubernetes")

        data = SDKData(
            metadata=meta,
            flows={"flow-a": flow_a, "flow-b": flow_b},
            work_pools={"k8s-pool": wp},
        )

        assert data.flow_count == 2
        assert data.deployment_count == 3
        assert data.work_pool_count == 1

    def test_deployment_names_derived(self):
        """Test that deployment_names is derived from flows."""
        meta = SDKGenerationMetadata(
            generation_time="2026-01-06T14:30:00Z",
            prefect_version="3.2.0",
        )

        dep1 = DeploymentInfo(
            name="production",
            flow_name="flow-a",
            full_name="flow-a/production",
        )
        dep2 = DeploymentInfo(
            name="staging",
            flow_name="flow-a",
            full_name="flow-a/staging",
        )
        dep3 = DeploymentInfo(
            name="daily",
            flow_name="flow-b",
            full_name="flow-b/daily",
        )

        flow_a = FlowInfo(name="flow-a", deployments=[dep1, dep2])
        flow_b = FlowInfo(name="flow-b", deployments=[dep3])

        data = SDKData(
            metadata=meta,
            flows={"flow-a": flow_a, "flow-b": flow_b},
        )

        # deployment_names should be derived from flows
        names = data.deployment_names
        assert len(names) == 3
        assert "flow-a/production" in names
        assert "flow-a/staging" in names
        assert "flow-b/daily" in names

    def test_all_deployments(self):
        meta = SDKGenerationMetadata(
            generation_time="2026-01-06T14:30:00Z",
            prefect_version="3.2.0",
        )

        dep1 = DeploymentInfo(
            name="production",
            flow_name="flow-a",
            full_name="flow-a/production",
        )
        dep2 = DeploymentInfo(
            name="staging",
            flow_name="flow-a",
            full_name="flow-a/staging",
        )
        dep3 = DeploymentInfo(
            name="daily",
            flow_name="flow-b",
            full_name="flow-b/daily",
        )

        flow_a = FlowInfo(name="flow-a", deployments=[dep1, dep2])
        flow_b = FlowInfo(name="flow-b", deployments=[dep3])

        data = SDKData(
            metadata=meta,
            flows={"flow-a": flow_a, "flow-b": flow_b},
        )

        all_deps = data.all_deployments()
        assert len(all_deps) == 3
        full_names = [d.full_name for d in all_deps]
        assert "flow-a/production" in full_names
        assert "flow-a/staging" in full_names
        assert "flow-b/daily" in full_names

    def test_all_deployments_empty(self):
        meta = SDKGenerationMetadata(
            generation_time="2026-01-06T14:30:00Z",
            prefect_version="3.2.0",
        )
        data = SDKData(metadata=meta)

        assert data.all_deployments() == []

    def test_deployment_names_sorted(self):
        """Test that deployment_names returns sorted names for deterministic output."""
        meta = SDKGenerationMetadata(
            generation_time="2026-01-06T14:30:00Z",
            prefect_version="3.2.0",
        )

        # Create deployments in non-alphabetical order
        dep_z = DeploymentInfo(name="z", flow_name="flow", full_name="flow/z")
        dep_a = DeploymentInfo(name="a", flow_name="flow", full_name="flow/a")
        dep_m = DeploymentInfo(name="m", flow_name="flow", full_name="flow/m")

        flow = FlowInfo(name="flow", deployments=[dep_z, dep_a, dep_m])

        data = SDKData(metadata=meta, flows={"flow": flow})

        # Should be sorted alphabetically
        assert data.deployment_names == ["flow/a", "flow/m", "flow/z"]

    def test_all_deployments_sorted(self):
        """Test that all_deployments returns sorted deployments for deterministic output."""
        meta = SDKGenerationMetadata(
            generation_time="2026-01-06T14:30:00Z",
            prefect_version="3.2.0",
        )

        # Create deployments in non-alphabetical order
        dep_z = DeploymentInfo(name="z", flow_name="flow", full_name="flow/z")
        dep_a = DeploymentInfo(name="a", flow_name="flow", full_name="flow/a")
        dep_m = DeploymentInfo(name="m", flow_name="flow", full_name="flow/m")

        flow = FlowInfo(name="flow", deployments=[dep_z, dep_a, dep_m])

        data = SDKData(metadata=meta, flows={"flow": flow})

        # Should be sorted by full_name
        all_deps = data.all_deployments()
        assert [d.full_name for d in all_deps] == ["flow/a", "flow/m", "flow/z"]


class TestDataModelIntegration:
    """Integration tests for data models working together."""

    def test_complete_sdk_data_structure(self):
        """Test building a complete SDKData structure like the generator would."""
        # Create metadata
        meta = SDKGenerationMetadata(
            generation_time="2026-01-06T14:30:00Z",
            prefect_version="3.2.0",
            workspace_name="my-workspace",
        )

        # Create work pool
        k8s_pool = WorkPoolInfo(
            name="kubernetes-pool",
            pool_type="kubernetes",
            job_variables_schema={
                "type": "object",
                "properties": {
                    "image": {"type": "string"},
                    "namespace": {"type": "string", "default": "default"},
                },
            },
        )

        # Create deployments
        etl_prod = DeploymentInfo(
            name="production",
            flow_name="my-etl-flow",
            full_name="my-etl-flow/production",
            parameter_schema={
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "batch_size": {"type": "integer", "default": 100},
                },
                "required": ["source"],
            },
            work_pool_name="kubernetes-pool",
            description="Production ETL pipeline",
        )

        etl_staging = DeploymentInfo(
            name="staging",
            flow_name="my-etl-flow",
            full_name="my-etl-flow/staging",
            parameter_schema={
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "batch_size": {"type": "integer", "default": 100},
                },
                "required": ["source"],
            },
            work_pool_name="kubernetes-pool",
        )

        # Create flow
        etl_flow = FlowInfo(
            name="my-etl-flow",
            deployments=[etl_prod, etl_staging],
        )

        # Build complete SDKData
        sdk_data = SDKData(
            metadata=meta,
            flows={"my-etl-flow": etl_flow},
            work_pools={"kubernetes-pool": k8s_pool},
        )

        # Verify structure
        assert sdk_data.flow_count == 1
        assert sdk_data.deployment_count == 2
        assert sdk_data.work_pool_count == 1
        assert len(sdk_data.deployment_names) == 2

        # Verify we can access nested data
        flow = sdk_data.flows["my-etl-flow"]
        assert len(flow.deployments) == 2

        deployment = flow.deployments[0]
        assert deployment.work_pool_name == "kubernetes-pool"
        assert deployment.parameter_schema is not None
        assert "source" in deployment.parameter_schema["properties"]

        work_pool = sdk_data.work_pools["kubernetes-pool"]
        assert "image" in work_pool.job_variables_schema["properties"]
