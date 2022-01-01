from unittest.mock import MagicMock

import box
import pytest

pytest.importorskip("google.cloud.aiplatform")

from prefect import config
from prefect.agent.vertex import VertexAgent
from prefect.run_configs import LocalRun, UniversalRun, VertexRun
from prefect.storage import Local
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult


@pytest.fixture(autouse=True)
def aiplatform(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr("prefect.agent.vertex.agent.get_client", lambda options: client)
    return client


@pytest.fixture
def project():
    return "example"


@pytest.fixture
def region():
    return "us-central1"


@pytest.fixture
def agent(project, region):
    return VertexAgent(project, region)


def graphql_result(run_config):
    return GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Local().serialize(),
                    "id": "flow-id",
                    "version": 1,
                    "name": "Test Flow",
                    "core_version": "0.13.0",
                }
            ),
            "run_config": run_config.serialize(),
            "id": "flow-run-id",
            "name": "flow-run-name",
        }
    )


def test_agent_defaults(agent, project, region):
    assert set(agent.labels) == set()
    assert agent.name == "agent"
    assert agent.project == project
    assert agent.service_account is None
    assert agent.client_options["api_endpoint"] == f"{region}-aiplatform.googleapis.com"


class TestEnvVars:
    DEFAULT = {
        "PREFECT__LOGGING__LEVEL": config.logging.level,
        "PREFECT__BACKEND": config.backend,
        "PREFECT__CLOUD__API": config.cloud.api,
        "PREFECT__CLOUD__AUTH_TOKEN": "",
        "PREFECT__CLOUD__API_KEY": "",
        "PREFECT__CLOUD__TENANT_ID": "",
        "PREFECT__CLOUD__AGENT__LABELS": "[]",
        "PREFECT__CLOUD__SEND_FLOW_RUN_LOGS": "true",
        "PREFECT__CONTEXT__FLOW_RUN_ID": "flow-run-id",
        "PREFECT__CONTEXT__FLOW_ID": "flow-id",
        "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
        "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
        "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
    }

    def test_environment_defaults(self, agent):
        run_config = UniversalRun()
        flow_run = graphql_result(run_config)

        env = agent.populate_env_vars(flow_run)
        assert env == self.DEFAULT

    def test_environment_overrides(self, project, region):
        # The precedent order is agent, then run, except for the required env vars
        agent = VertexAgent(
            project,
            region,
            env_vars={"a": 0, "b": 2, "PREFECT__LOGGING__LEVEL": "test0"},
        )
        run_config = UniversalRun(
            env={"a": 1, "c": 2, "PREFECT__LOGGING__LEVEL": "test1"}
        )
        flow_run = graphql_result(run_config)

        env = agent.populate_env_vars(flow_run)
        expected = self.DEFAULT.copy()
        expected["PREFECT__LOGGING__LEVEL"] = "test1"
        expected["a"] = 1
        expected["b"] = 2
        expected["c"] = 2
        assert env == expected

    @pytest.mark.parametrize("tenant_id", ["ID", None])
    def test_environment_has_api_key_from_config(self, agent, tenant_id):
        with set_temporary_config(
            {
                "cloud.api_key": "TEST_KEY",
                "cloud.tenant_id": tenant_id,
                "cloud.agent.auth_token": None,
            }
        ):
            run_config = UniversalRun()
            flow_run = graphql_result(run_config)
            env = agent.populate_env_vars(flow_run)

        expected = self.DEFAULT.copy()
        expected["PREFECT__CLOUD__API_KEY"] == "TEST_KEY"
        expected["PREFECT__CLOUD__AUTH_TOKEN"] == "TEST_KEY"
        expected["PREFECT__CLOUD__TENANT_ID"] == "ID"
        assert env == expected

    def test_environment_has_agent_token_from_config(self, agent):
        with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
            run_config = UniversalRun()
            flow_run = graphql_result(run_config)
            env = agent.populate_env_vars(flow_run)

        expected = self.DEFAULT.copy()
        expected["PREFECT__CLOUD__AUTH_TOKEN"] = "TEST_TOKEN"
        assert env == expected


class TestGenerateTaskDefinition:
    def test_env_list(self, agent):
        # test to ensure the content in the env list is the expected format
        run_config = UniversalRun(env={"a": 1})
        flow_run = graphql_result(run_config)
        task_def = agent.generate_task_definition(flow_run)

        env_list = task_def["job_spec"]["worker_pool_specs"][0]["container_spec"]["env"]
        assert {"name": "a", "value": 1} in env_list

    def test_generate_task_definition_defaults(self, agent):
        run_config = UniversalRun()
        flow_run = graphql_result(run_config)
        task_def = agent.generate_task_definition(flow_run)
        job_spec = task_def["job_spec"]
        pool_spec = job_spec["worker_pool_specs"][0]
        env_list = agent._to_env_list(agent.populate_env_vars(flow_run))

        assert task_def["display_name"]

        for unspecified in ["network", "service_account", "scheduling"]:
            assert job_spec.get(unspecified) is None

        assert pool_spec["machine_spec"] == {"machine_type": "e2-standard-4"}
        assert pool_spec["replica_count"] == 1
        assert pool_spec["container_spec"] == {
            "image_uri": "prefecthq/prefect:0.13.0",  # from the core version above
            "command": ["prefect", "execute", "flow-run"],
            "args": [],
            "env": env_list,
        }

    def test_generate_task_definition_simple(self, agent):
        # These are set inside the pool spec
        run_config = VertexRun(
            image="prefecthq/prefect:xyz",
            machine_type="e2-highmem-16",
        )
        flow_run = graphql_result(run_config)
        task_def = agent.generate_task_definition(flow_run)
        job_spec = task_def["job_spec"]
        pool_spec = job_spec["worker_pool_specs"][0]
        env_list = agent._to_env_list(agent.populate_env_vars(flow_run))

        assert task_def["display_name"]

        for unspecified in ["network", "service_account", "scheduling"]:
            assert job_spec.get(unspecified) is None

        assert pool_spec["machine_spec"] == {"machine_type": "e2-highmem-16"}
        assert pool_spec["replica_count"] == 1
        assert pool_spec["container_spec"] == {
            "image_uri": "prefecthq/prefect:xyz",
            "command": ["prefect", "execute", "flow-run"],
            "args": [],
            "env": env_list,
        }

    def test_generate_task_definition_customization(self, agent):
        machine_spec = {
            "machine_type": "e2-standard-16",
            "acceleratorType": "NVIDIA_TESLA_K80",
            "acceleartorCount": 1,
        }
        run_config = VertexRun(
            image="prefecthq/prefect:xyz",  # should be used
            machine_type="e2-highmem-16",  # should not be used
            scheduling={"a": 1},
            service_account="b",
            network="c",
            worker_pool_specs=[
                {
                    "machine_spec": machine_spec,
                    "container_spec": {
                        "image_uri": "prefecthq/prefect:abc"
                    },  # This should be overwritten
                }
            ],
        )
        flow_run = graphql_result(run_config)
        task_def = agent.generate_task_definition(flow_run)
        job_spec = task_def["job_spec"]
        pool_spec = job_spec["worker_pool_specs"][0]
        env_list = agent._to_env_list(agent.populate_env_vars(flow_run))

        assert task_def["display_name"]

        assert job_spec["scheduling"] == {"a": 1}
        assert job_spec["network"] == "c"
        assert job_spec["service_account"] == "b"

        assert pool_spec["machine_spec"] == machine_spec
        assert pool_spec["container_spec"] == {
            "image_uri": "prefecthq/prefect:xyz",  # from the core version above
            "command": ["prefect", "execute", "flow-run"],
            "args": [],
            "env": env_list,
        }


class TestDeployFlow:
    DEFAULT_JOB = {
        "display_name": "test-flow-flow-run-name",
        "job_spec": {
            "worker_pool_specs": [
                {
                    "machine_spec": {"machine_type": "e2-standard-4"},
                    "replica_count": 1,
                    "container_spec": {
                        "image_uri": "prefecthq/prefect:0.13.0",
                        "command": ["prefect", "execute", "flow-run"],
                        "args": [],
                        "env": [
                            {
                                "name": "PREFECT__LOGGING__LEVEL",
                                "value": config.logging.level,
                            },
                            {"name": "PREFECT__BACKEND", "value": config.backend},
                            {
                                "name": "PREFECT__CLOUD__API",
                                "value": config.cloud.api,
                            },
                            {"name": "PREFECT__CLOUD__AUTH_TOKEN", "value": ""},
                            {"name": "PREFECT__CLOUD__API_KEY", "value": ""},
                            {"name": "PREFECT__CLOUD__TENANT_ID", "value": ""},
                            {"name": "PREFECT__CLOUD__AGENT__LABELS", "value": "[]"},
                            {
                                "name": "PREFECT__CLOUD__SEND_FLOW_RUN_LOGS",
                                "value": "true",
                            },
                            {
                                "name": "PREFECT__CONTEXT__FLOW_RUN_ID",
                                "value": "flow-run-id",
                            },
                            {"name": "PREFECT__CONTEXT__FLOW_ID", "value": "flow-id"},
                            {
                                "name": "PREFECT__CLOUD__USE_LOCAL_SECRETS",
                                "value": "false",
                            },
                            {
                                "name": "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS",
                                "value": "prefect.engine.cloud.CloudFlowRunner",
                            },
                            {
                                "name": "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS",
                                "value": "prefect.engine.cloud.CloudTaskRunner",
                            },
                            {"name": "PREFECT__LOGGING__LOG_TO_CLOUD", "value": "true"},
                        ],
                    },
                }
            ],
            "service_account": None,
        },
    }

    def deploy_flow(self, agent, run_config):
        flow_run = graphql_result(run_config)
        return agent.deploy_flow(flow_run)

    def test_deploy_flow_errors_if_not_vertex_run_config(self, agent):
        with pytest.raises(
            TypeError,
            match="`run_config` of type `LocalRun`, only `VertexRun` is supported",
        ):
            self.deploy_flow(agent, LocalRun())

    def test_deploy_flow_job_spec(self, aiplatform, agent, region, project):
        aiplatform.create_custom_job.return_value = box.Box(
            name="/projects/abc/locations/us-central1/customJobs/custom_job_name"
        )
        result = self.deploy_flow(agent, UniversalRun())

        # Check that we repsected the vertex response name in the url info
        assert result.endswith(f"{agent.region_name}/training/custom_job_name")

        aiplatform.create_custom_job.assert_called_once()

        # correct region and project
        assert (
            aiplatform.create_custom_job.call_args[1]["parent"]
            == f"projects/{project}/locations/{region}"
        )
        # correct job spec for a default job
        assert (
            aiplatform.create_custom_job.call_args[1]["custom_job"] == self.DEFAULT_JOB
        )
