import logging
import jwt
import pytest
from prefect.engine.signals import FAIL
from prefect.tasks.cubejs import CubeJSQueryTask
import responses
from urllib.parse import quote_plus


class TestCubeJSQueryTask:
    def test_construction_no_values(self):
        cubejs_task = CubeJSQueryTask()

        assert cubejs_task.subdomain is None
        assert cubejs_task.url is None
        assert cubejs_task.api_secret is None
        assert cubejs_task.api_secret_env_var == "CUBEJS_API_SECRET"
        assert cubejs_task.query is None
        assert not cubejs_task.include_generated_sql
        assert cubejs_task.security_context is None

    def test_construction_with_values(self):
        cubejs_task = CubeJSQueryTask(
            subdomain="foo",
            url="http://bar",
            api_secret="secret",
            api_secret_env_var="secret_env_var",
            query={"measures": "count"},
            include_generated_sql=True,
            security_context={"foo": "bar"},
        )

        assert cubejs_task.subdomain == "foo"
        assert cubejs_task.url == "http://bar"
        assert cubejs_task.api_secret == "secret"
        assert cubejs_task.api_secret_env_var == "secret_env_var"
        assert cubejs_task.query == {"measures": "count"}
        assert cubejs_task.include_generated_sql
        assert cubejs_task.security_context == {"foo": "bar"}

    def test_run_with_no_values_raises(self):
        cubejs_task = CubeJSQueryTask()
        msg_match = "Missing both `subdomain` and `url`."
        with pytest.raises(ValueError, match=msg_match):
            cubejs_task.run()

    def test_run_without_api_secret_api_secret_env_var(self):
        cubejs_task = CubeJSQueryTask()
        msg_match = "Missing `api_secret` and `api_secret_env_var` not found."
        with pytest.raises(ValueError, match=msg_match):
            cubejs_task.run(subdomain="foo")

    def test_run_without_query_raises(self):
        cubejs_task = CubeJSQueryTask()
        msg_match = "Missing `query`."
        with pytest.raises(ValueError, match=msg_match):
            cubejs_task.run(subdomain="foo", api_secret="bar")

    @responses.activate
    def test_run_with_failing_api_raises(self):
        cubejs_task = CubeJSQueryTask()
        msg_match = "Cube.js load API failed!"
        responses.add(
            responses.GET, "https://test.cubecloud.dev/cubejs-api/v1/load", status=123
        )

        with pytest.raises(FAIL, match=msg_match):
            cubejs_task.run(
                subdomain="test", api_secret="foo", query={"measures": "count"}
            )

    @responses.activate
    def test_run_with_continue_waiting(self, caplog):
        api_url = "https://test.cubecloud.dev/cubejs-api/v1/load"
        cubejs_task = CubeJSQueryTask()

        responses.add(
            responses.GET,
            api_url,
            status=200,
            json={"error": "Continue wait"},
        )

        responses.add(
            responses.GET,
            api_url,
            status=200,
            json={"data": "result"},
        )

        data = cubejs_task.run(
            subdomain="test", api_secret="foo", query={"measures": "count"}
        )

        expected_url = api_url + "?query=" + quote_plus('{"measures": "count"}')

        assert responses.assert_call_count(expected_url, 2) is True
        assert isinstance(data, dict)

    @responses.activate
    def test_run_with_security_context(self, caplog):
        caplog.set_level(logging.DEBUG)
        cubejs_task = CubeJSQueryTask()

        responses.add(
            responses.GET,
            "https://test.cubecloud.dev/cubejs-api/v1/load",
            status=200,
            json={"data": "result"},
        )

        cubejs_task.run(
            subdomain="test",
            api_secret="foo",
            query={"measures": "count"},
            security_context={"foo": "bar"},
        )

        expected_jwt = jwt.encode(
            payload={"foo": "bar", "expiresIn": "7d"}, key="foo", algorithm="HS256"
        )

        assert responses.calls[0].request.headers["Authorization"] == expected_jwt

    @responses.activate
    def test_run_with_max_wait_time_raises(self):
        cubejs_task = CubeJSQueryTask()
        msg_match = "Cube.js load API took longer than 3 seconds to provide a response."
        responses.add(
            responses.GET,
            "https://test.cubecloud.dev/cubejs-api/v1/load",
            status=200,
            json={"error": "Continue wait"},
        )

        with pytest.raises(FAIL, match=msg_match):
            cubejs_task.run(
                subdomain="test",
                api_secret="foo",
                query={"measures": "count"},
                security_context={"foo": "bar"},
                wait_time_between_api_calls=1,
                max_wait_time=3,
            )

    @responses.activate
    def test_run_with_include_generated_sql(self):
        cubejs_task = CubeJSQueryTask()

        responses.add(
            responses.GET,
            "https://test.cubecloud.dev/cubejs-api/v1/load",
            status=200,
            json={"data": "result"},
        )

        responses.add(
            responses.GET,
            "https://test.cubecloud.dev/cubejs-api/v1/sql",
            status=200,
            json={"sql": "sql"},
        )

        data = cubejs_task.run(
            subdomain="test",
            api_secret="foo",
            query={"measures": "count"},
            include_generated_sql=True,
        )

        assert isinstance(data, dict)
        assert "data" in data.keys()
        assert "sql" in data.keys()
