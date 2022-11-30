import pytest
from prefect.engine.signals import LOOP, FAIL
from prefect.tasks.cubejs import CubePreAggregationsBuildTask
import responses

security_context = {
    "expiresIn": 1,
    "foo": "bar",
}

selector = {
    "action": "post",
    "selector": {
        "contexts": [
            {"securityContext": {"tenant": "t1"}},
            {"securityContext": {"tenant": "t2"}},
        ],
        "timezones": ["UTC", "America/Los_Angeles"],
    },
}

response_tokens = [
    "be598e318484848cbb06291baa59ca3a",
    "d4bb22530aa9905219b2f0e6a214c39f",
    "e1578a60514a7c55689016adf0863965",
]

response_status_missing_partition = {
    "e1578a60514a7c55689016adf0863965": {
        "table": "preaggs.e_commerce__manual_updates20201201_kuggpskn_alfb3s4u_1hmrdkc",
        "status": "missing_partition",
        "selector": {
            "cubes": ["ECommerce"],
            "preAggregations": ["ECommerce.ManualUpdates"],
            "contexts": [{"securityContext": {"tenant": "t2"}}],
            "timezones": ["America/Los_Angeles"],
            "dataSources": ["default"],
        },
    },
    "d4bb22530aa9905219b2f0e6a214c39f": {
        "table": "preaggs.e_commerce__manual_updates20201101_rvfrwirb_ucnfhp2g_1hmrdkc",
        "status": "missing_partition",
        "selector": {
            "cubes": ["ECommerce"],
            "preAggregations": ["ECommerce.ManualUpdates"],
            "contexts": [{"securityContext": {"tenant": "t2"}}],
            "timezones": ["America/Los_Angeles"],
            "dataSources": ["default"],
        },
    },
    "be598e318484848cbb06291baa59ca3a": {
        "table": "preaggs.e_commerce__manual_updates20201201_kbn0y0iy_fvfip33o_1hmrdkc",
        "status": "missing_partition",
        "selector": {
            "cubes": ["ECommerce"],
            "preAggregations": ["ECommerce.ManualUpdates"],
            "contexts": [{"securityContext": {"tenant": "t2"}}],
            "timezones": ["UTC"],
            "dataSources": ["default"],
        },
    },
}

response_status_failure = {
    "e1578a60514a7c55689016adf0863965": {
        "table": "preaggs.e_commerce__manual_updates20201201_kuggpskn_alfb3s4u_1hmrdkc",
        "status": "done",
        "selector": {
            "cubes": ["ECommerce"],
            "preAggregations": ["ECommerce.ManualUpdates"],
            "contexts": [{"securityContext": {"tenant": "t2"}}],
            "timezones": ["America/Los_Angeles"],
            "dataSources": ["default"],
        },
    },
    "d4bb22530aa9905219b2f0e6a214c39f": {
        "table": "preaggs.e_commerce__manual_updates20201101_rvfrwirb_ucnfhp2g_1hmrdkc",
        "status": "done",
        "selector": {
            "cubes": ["ECommerce"],
            "preAggregations": ["ECommerce.ManualUpdates"],
            "contexts": [{"securityContext": {"tenant": "t2"}}],
            "timezones": ["America/Los_Angeles"],
            "dataSources": ["default"],
        },
    },
    "be598e318484848cbb06291baa59ca3a": {
        "table": "preaggs.e_commerce__manual_updates20201201_kbn0y0iy_fvfip33o_1hmrdkc",
        "status": "failure: returned error",
        "selector": {
            "cubes": ["ECommerce"],
            "preAggregations": ["ECommerce.ManualUpdates"],
            "contexts": [{"securityContext": {"tenant": "t2"}}],
            "timezones": ["UTC"],
            "dataSources": ["default"],
        },
    },
}

response_status_processing = {
    "e1578a60514a7c55689016adf0863965": {
        "table": "preaggs.e_commerce__manual_updates20201201_kuggpskn_alfb3s4u_1hmrdkc",
        "status": "done",
        "selector": {
            "cubes": ["ECommerce"],
            "preAggregations": ["ECommerce.ManualUpdates"],
            "contexts": [{"securityContext": {"tenant": "t2"}}],
            "timezones": ["America/Los_Angeles"],
            "dataSources": ["default"],
        },
    },
    "d4bb22530aa9905219b2f0e6a214c39f": {
        "table": "preaggs.e_commerce__manual_updates20201101_rvfrwirb_ucnfhp2g_1hmrdkc",
        "status": "processing",
        "selector": {
            "cubes": ["ECommerce"],
            "preAggregations": ["ECommerce.ManualUpdates"],
            "contexts": [{"securityContext": {"tenant": "t2"}}],
            "timezones": ["America/Los_Angeles"],
            "dataSources": ["default"],
        },
    },
    "be598e318484848cbb06291baa59ca3a": {
        "table": "preaggs.e_commerce__manual_updates20201201_kbn0y0iy_fvfip33o_1hmrdkc",
        "status": "scheduled",
        "selector": {
            "cubes": ["ECommerce"],
            "preAggregations": ["ECommerce.ManualUpdates"],
            "contexts": [{"securityContext": {"tenant": "t2"}}],
            "timezones": ["UTC"],
            "dataSources": ["default"],
        },
    },
}

response_status_done = {
    "e1578a60514a7c55689016adf0863965": {
        "table": "preaggs.e_commerce__manual_updates20201201_kuggpskn_alfb3s4u_1hmrdkc",
        "status": "done",
        "selector": {
            "cubes": ["ECommerce"],
            "preAggregations": ["ECommerce.ManualUpdates"],
            "contexts": [{"securityContext": {"tenant": "t2"}}],
            "timezones": ["America/Los_Angeles"],
            "dataSources": ["default"],
        },
    },
    "d4bb22530aa9905219b2f0e6a214c39f": {
        "table": "preaggs.e_commerce__manual_updates20201101_rvfrwirb_ucnfhp2g_1hmrdkc",
        "status": "done",
        "selector": {
            "cubes": ["ECommerce"],
            "preAggregations": ["ECommerce.ManualUpdates"],
            "contexts": [{"securityContext": {"tenant": "t2"}}],
            "timezones": ["America/Los_Angeles"],
            "dataSources": ["default"],
        },
    },
    "be598e318484848cbb06291baa59ca3a": {
        "table": "preaggs.e_commerce__manual_updates20201201_kbn0y0iy_fvfip33o_1hmrdkc",
        "status": "done",
        "selector": {
            "cubes": ["ECommerce"],
            "preAggregations": ["ECommerce.ManualUpdates"],
            "contexts": [{"securityContext": {"tenant": "t2"}}],
            "timezones": ["UTC"],
            "dataSources": ["default"],
        },
    },
}


class TestCubePreAggregationsBuildTask:
    """
    run: pytest -s tests/tasks/cubejs/test_cube_jobs_tasks.py
    console: print()
    """

    def test_construction_no_values(self):
        try:
            CubePreAggregationsBuildTask()
            assert False
        except Exception:
            assert True

    def test_construction_no_secret(self):
        try:
            CubePreAggregationsBuildTask(
                url="http://localhost:4000/cubejs-system",
            )
            assert False
        except Exception:
            assert True

    def test_construction_min_required(self):
        task = CubePreAggregationsBuildTask(
            url="http://localhost:4000/cubejs-system",
            api_secret="23dff8b29cf20df38a4c78dfaf689fa55916add4d27ee3dd9ba75d14732aafa3",
        )
        assert task.subdomain is None
        assert task.url == "http://localhost:4000/cubejs-system"
        assert (
            task.api_secret
            == "23dff8b29cf20df38a4c78dfaf689fa55916add4d27ee3dd9ba75d14732aafa3"
        )
        assert task.security_context is None
        assert task.selector is None
        assert not task.wait_for_job_run_completion
        assert task.wait_time_between_api_calls == 10
        assert task.cubejs_client

    def test_construction_with_values(self):
        task = CubePreAggregationsBuildTask(
            subdomain="subdomain",
            url="http://localhost:4000/cubejs-system",
            api_secret="23dff8b29cf20df38a4c78dfaf689fa55916add4d27ee3dd9ba75d14732aafa3",
            security_context=security_context,
            selector=selector,
            wait_for_job_run_completion=True,
            wait_time_between_api_calls=5,
        )
        assert task.subdomain == "subdomain"
        assert task.url == "http://localhost:4000/cubejs-system"
        assert (
            task.api_secret
            == "23dff8b29cf20df38a4c78dfaf689fa55916add4d27ee3dd9ba75d14732aafa3"
        )
        assert task.security_context == security_context
        assert task.selector == selector
        assert task.wait_for_job_run_completion
        assert task.wait_time_between_api_calls == 5
        assert task.cubejs_client

    def test_run_without_selector_raises(self):
        task = CubePreAggregationsBuildTask(
            url="http://localhost:4000/cubejs-system",
            api_secret="23dff8b29cf20df38a4c78dfaf689fa55916add4d27ee3dd9ba75d14732aafa3",
        )
        msg_match = "Missing `selector`."
        with pytest.raises(ValueError, match=msg_match):
            task.run()

    @responses.activate
    def test_run_internal_error_raises(self):
        task = CubePreAggregationsBuildTask(
            url="http://localhost:4000/cubejs-system",
            api_secret="23dff8b29cf20df38a4c78dfaf689fa55916add4d27ee3dd9ba75d14732aafa3",
        )
        msg_match = (
            "Cube `pre-aggregations/jobs` API failed! Error is: Internal Server Error"
        )
        responses.add(
            responses.POST,
            "http://localhost:4000/cubejs-system/v1/pre-aggregations/jobs",
            json={"error": "500"},
            status=500,
        )
        with pytest.raises(FAIL, match=msg_match):
            task.run(selector=selector)

    @responses.activate
    def test_run_no_completion(self):
        task = CubePreAggregationsBuildTask(
            url="http://localhost:4000/cubejs-system",
            api_secret="23dff8b29cf20df38a4c78dfaf689fa55916add4d27ee3dd9ba75d14732aafa3",
        )
        responses.add(
            responses.POST,
            "http://localhost:4000/cubejs-system/v1/pre-aggregations/jobs",
            json=response_tokens,
            status=200,
        )
        task.run(selector=selector)
        assert len(responses.calls) == 1

    @responses.activate
    def test_run_completion_one_step(self):
        task = CubePreAggregationsBuildTask(
            url="http://localhost:4000/cubejs-system",
            api_secret="23dff8b29cf20df38a4c78dfaf689fa55916add4d27ee3dd9ba75d14732aafa3",
            wait_for_job_run_completion=True,
            wait_time_between_api_calls=0,
        )
        responses.add(
            responses.POST,
            "http://localhost:4000/cubejs-system/v1/pre-aggregations/jobs",
            json=response_tokens,
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:4000/cubejs-system/v1/pre-aggregations/jobs",
            json=response_status_done,
            status=200,
        )
        task.run(selector=selector)
        assert len(responses.calls) == 2

    @responses.activate
    def test_run_completion_two_step(self):
        task = CubePreAggregationsBuildTask(
            url="http://localhost:4000/cubejs-system",
            api_secret="23dff8b29cf20df38a4c78dfaf689fa55916add4d27ee3dd9ba75d14732aafa3",
            wait_for_job_run_completion=True,
            wait_time_between_api_calls=0,
        )
        responses.add(
            responses.POST,
            "http://localhost:4000/cubejs-system/v1/pre-aggregations/jobs",
            json=response_tokens,
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:4000/cubejs-system/v1/pre-aggregations/jobs",
            json=response_status_processing,
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:4000/cubejs-system/v1/pre-aggregations/jobs",
            json=response_status_done,
            status=200,
        )
        msg_match = "looping..."
        with pytest.raises(LOOP, match=msg_match):
            task.run(selector=selector)
            assert len(responses.calls) == 3

    @responses.activate
    def test_run_completion_three_step(self):
        task = CubePreAggregationsBuildTask(
            url="http://localhost:4000/cubejs-system",
            api_secret="23dff8b29cf20df38a4c78dfaf689fa55916add4d27ee3dd9ba75d14732aafa3",
            wait_for_job_run_completion=True,
            wait_time_between_api_calls=0,
        )
        responses.add(
            responses.POST,
            "http://localhost:4000/cubejs-system/v1/pre-aggregations/jobs",
            json=response_tokens,
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:4000/cubejs-system/v1/pre-aggregations/jobs",
            json=response_status_processing,
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:4000/cubejs-system/v1/pre-aggregations/jobs",
            json=response_status_processing,
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:4000/cubejs-system/v1/pre-aggregations/jobs",
            json=response_status_done,
            status=200,
        )
        msg_match = "looping..."
        with pytest.raises(LOOP, match=msg_match):
            task.run(selector=selector)
            assert len(responses.calls) == 4

    @responses.activate
    def test_run_completion_missing_partitions_raises(self):
        task = CubePreAggregationsBuildTask(
            url="http://localhost:4000/cubejs-system",
            api_secret="23dff8b29cf20df38a4c78dfaf689fa55916add4d27ee3dd9ba75d14732aafa3",
            wait_for_job_run_completion=True,
            wait_time_between_api_calls=0,
        )
        responses.add(
            responses.POST,
            "http://localhost:4000/cubejs-system/v1/pre-aggregations/jobs",
            json=response_tokens,
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:4000/cubejs-system/v1/pre-aggregations/jobs",
            json=response_status_missing_partition,
            status=200,
        )
        msg_match = "Cube pre-aggregations build failed: missing partitions."
        with pytest.raises(FAIL, match=msg_match):
            task.run(selector=selector)
            assert len(responses.calls) == 2

    @responses.activate
    def test_run_completion_failure_raises(self):
        task = CubePreAggregationsBuildTask(
            url="http://localhost:4000/cubejs-system",
            api_secret="23dff8b29cf20df38a4c78dfaf689fa55916add4d27ee3dd9ba75d14732aafa3",
            wait_for_job_run_completion=True,
            wait_time_between_api_calls=0,
        )
        responses.add(
            responses.POST,
            "http://localhost:4000/cubejs-system/v1/pre-aggregations/jobs",
            json=response_tokens,
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:4000/cubejs-system/v1/pre-aggregations/jobs",
            json=response_status_failure,
            status=200,
        )
        msg_match = "Cube pre-aggregations build failed: failure: returned error."
        with pytest.raises(FAIL, match=msg_match):
            task.run(selector=selector)
            assert len(responses.calls) == 2
