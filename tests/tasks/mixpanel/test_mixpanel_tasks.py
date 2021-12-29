import base64
from datetime import date
import os
import pytest
import responses
from unittest.mock import patch

from prefect.tasks.mixpanel import MixpanelExportTask

from prefect.engine.signals import FAIL


class TestMixpanelTasks:
    def test_construction_mixpanel_export_task(self):
        expected_api_secret = "foo_secret"
        expected_api_secret_env_var = "foo_env_var_secret"
        expected_from_date = "2011-07-10"
        expected_to_date = date.today().strftime("%Y-%m-%d")
        expected_limit = 1
        expected_event = ["foo_event"]

        mx_export_task = MixpanelExportTask(
            api_secret="foo_secret",
            api_secret_env_var="foo_env_var_secret",
            limit=1,
            event=["foo_event"],
            use_eu_server=True,
        )

        assert mx_export_task.api_secret == expected_api_secret
        assert mx_export_task.api_secret_env_var == expected_api_secret_env_var
        assert mx_export_task.from_date == expected_from_date
        assert mx_export_task.to_date == expected_to_date
        assert mx_export_task.limit == expected_limit
        assert mx_export_task.event == expected_event
        assert mx_export_task.where is None
        assert mx_export_task.parse_response is False
        assert mx_export_task.use_eu_server is True

    def test_construction_string_event(self):
        expected_event = '["foo"]'

        mx_export_task = MixpanelExportTask(event='["foo"]')

        assert mx_export_task.event == expected_event

    def test_construction_list_of_string_event(self):
        expected_event = ["foo"]

        mx_export_task = MixpanelExportTask(event=["foo"])

        assert mx_export_task.event == expected_event

    def test_run_missing_both_api_secret_and_env_var_raises(self):
        msg_match = "Missing both `api_secret` and `api_secret_env_var`."
        with pytest.raises(ValueError, match=msg_match):
            MixpanelExportTask().run()

        # assert "Missing both `api_secret` and `api_secret_env_var`." in str(exc)

    def test_run_missing_api_secret_not_found_env_var_raises(self):
        msg_match = "Missing `api_secret` and `api_secret_env_var` not found."
        with pytest.raises(ValueError, match=msg_match):
            MixpanelExportTask().run(api_secret_env_var="foo")

        # assert "Missing `api_secret` and `api_secret_env_var` not found." in str(exc)

    @responses.activate
    def test_run_secret_from_api_secret(self, caplog):
        today = date.today().strftime("%Y-%m-%d")
        url = f"https://data.mixpanel.com/api/2.0/export?from_date=2011-07-10&to_date={today}"
        responses.add(responses.GET, url, status=200)

        mx_export_task = MixpanelExportTask()

        secret = "foo"
        mx_export_task.run(api_secret=secret)

        secret_bytes = f"{secret}:".encode("ascii")
        secret_b64_bytes = base64.b64encode(secret_bytes)
        secret_message = secret_b64_bytes.decode("ascii")
        authorization = f"Basic {secret_message}"

        assert responses.calls[0].request.headers["Authorization"] == authorization

    @patch.dict(os.environ, {"foo": "bar"})
    @responses.activate
    def test_run_secret_from_api_secret_env_var(self, caplog):

        today = date.today().strftime("%Y-%m-%d")
        url = f"https://data.mixpanel.com/api/2.0/export?from_date=2011-07-10&to_date={today}"
        responses.add(responses.GET, url, status=200)

        mx_export_task = MixpanelExportTask()

        secret_env_var = "foo"
        mx_export_task.run(api_secret_env_var=secret_env_var)
        secret = os.environ[secret_env_var]

        secret_bytes = f"{secret}:".encode("ascii")
        secret_b64_bytes = base64.b64encode(secret_bytes)
        secret_message = secret_b64_bytes.decode("ascii")
        authorization = f"Basic {secret_message}"

        assert responses.calls[0].request.headers["Authorization"] == authorization

    @responses.activate
    def test_run_empty_result_without_parse(self):
        today = date.today().strftime("%Y-%m-%d")
        url = f"https://data.mixpanel.com/api/2.0/export?from_date=2011-07-10&to_date={today}"
        responses.add(responses.GET, url, status=200, body="")

        mx_export_task = MixpanelExportTask()
        ret = mx_export_task.run(api_secret="foo")

        assert ret is None

    @responses.activate
    def test_run_empty_result_with_parse(self):
        today = date.today().strftime("%Y-%m-%d")
        url = f"https://data.mixpanel.com/api/2.0/export?from_date=2011-07-10&to_date={today}"
        responses.add(responses.GET, url, status=200, body="")

        mx_export_task = MixpanelExportTask()
        ret = mx_export_task.run(api_secret="foo", parse_response=True)

        assert ret is None

    @responses.activate
    def test_run_without_parse(self):
        today = date.today().strftime("%Y-%m-%d")
        url = f"https://data.mixpanel.com/api/2.0/export?from_date=2011-07-10&to_date={today}"
        responses.add(
            responses.GET, url, status=200, body='{"foo": "bar"}\n{"alice": "bob"}'
        )

        mx_export_task = MixpanelExportTask()
        ret = mx_export_task.run(api_secret="foo")

        assert ret == '{"foo": "bar"}\n{"alice": "bob"}'

    @responses.activate
    def test_run_with_parse(self):
        today = date.today().strftime("%Y-%m-%d")
        url = f"https://data.mixpanel.com/api/2.0/export?from_date=2011-07-10&to_date={today}"
        responses.add(
            responses.GET, url, status=200, body='{"foo": "bar"}\n{"alice": "bob"}'
        )

        mx_export_task = MixpanelExportTask()
        ret = mx_export_task.run(api_secret="foo", parse_response=True)

        assert ret == [{"foo": "bar"}, {"alice": "bob"}]

    @responses.activate
    def test_run_with_parse_and_group(self):
        today = date.today().strftime("%Y-%m-%d")
        url = f"https://data.mixpanel.com/api/2.0/export?from_date=2011-07-10&to_date={today}"
        event1 = '{"event": "alice", "properties": {"p1": "v1"}}'
        event2 = '{"event": "bob", "properties": {"p1": "v1"}}'
        event3 = '{"event": "bob", "properties": {"p2": "v2"}}'
        body = "\n".join([event1, event2, event3])
        responses.add(responses.GET, url, status=200, body=body)

        mx_export_task = MixpanelExportTask()
        ret = mx_export_task.run(
            api_secret="foo", parse_response=True, group_events=True
        )

        assert ret == {"alice": [{"p1": "v1"}], "bob": [{"p1": "v1"}, {"p2": "v2"}]}

    @responses.activate
    def test_run_raises_fail(self):
        url = "https://data.mixpanel.com/api/2.0/export?from_date=abc&to_date=abc"
        responses.add(responses.GET, url, status=123, body="mixpanel error")

        mx_export_task = MixpanelExportTask()

        with pytest.raises(FAIL, match="Mixpanel export API error."):
            mx_export_task.run(api_secret="foo", from_date="abc", to_date="abc")
