from datetime import date
import logging
import os
import pytest
import responses
from unittest.mock import patch

from prefect.tasks.mixpanel.mixpanel_tasks import MixpanelExportTask


class TestMixpanelTasks:
    def test_construction_mixpanel_export_task(self):
        expected_api_secret = "foo_secret"
        expected_api_secret_env_var = "foo_env_var_secret"
        expected_from_date = "1900-01-01"
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
        with pytest.raises(ValueError) as exc:
            MixpanelExportTask().run()

        assert "Missing both `api_secret` and `api_secret_env_var`." in str(exc)

    def test_run_missing_api_secret_not_found_env_var_raises(self):
        with pytest.raises(ValueError) as exc:
            MixpanelExportTask().run(api_secret_env_var="foo")

        assert "Missing `api_secret` and `api_secret_env_var` not found." in str(exc)

    @responses.activate
    def test_run_secret_from_api_secret(self, caplog):
        caplog.set_level(logging.DEBUG)

        today = date.today().strftime("%Y-%m-%d")
        url = f"https://data.mixpanel.com/api/2.0/export?from_date=1900-01-01&to_date={today}"
        responses.add(responses.GET, url, status=200)

        mx_export_task = MixpanelExportTask()
        mx_export_task.run(api_secret="foo")

        assert "Got secret from `api_secret`" in caplog.text

    @patch.dict(os.environ, {"foo": "bar"})
    @responses.activate
    def test_run_secret_from_api_secret_env_var(self, caplog):
        caplog.set_level(logging.DEBUG)

        today = date.today().strftime("%Y-%m-%d")
        url = f"https://data.mixpanel.com/api/2.0/export?from_date=1900-01-01&to_date={today}"
        responses.add(responses.GET, url, status=200)

        mx_export_task = MixpanelExportTask()
        mx_export_task.run(api_secret_env_var="foo")

        assert "Got secret from env var passed from `api_secret_env_var`" in caplog.text
