import os
import pytest
import responses
from unittest.mock import patch

from prefect.tasks.hightouch import HightouchRunSync
from prefect.engine.signals import FAIL


class TestHightouchRunSyncTask:
    def test_construction_no_values(self):
        ht_task = HightouchRunSync()

        assert ht_task.api_key is None
        assert ht_task.api_key_env_var is None
        assert ht_task.sync_id is None
        assert ht_task.wait_for_completion is False
        assert ht_task.wait_time_between_api_calls == 10
        assert ht_task.max_wait_time is None

    def test_construction_with_values(self):
        ht_task = HightouchRunSync(
            api_key="key",
            api_key_env_var="key_env_var",
            sync_id=123,
            wait_for_completion=True,
            wait_time_between_api_calls=123,
            max_wait_time=123,
        )

        assert ht_task.api_key == "key"
        assert ht_task.api_key_env_var == "key_env_var"
        assert ht_task.sync_id == 123
        assert ht_task.wait_for_completion is True
        assert ht_task.wait_time_between_api_calls == 123
        assert ht_task.max_wait_time == 123

    def test_run_with_no_values_raises(self):
        ht_task = HightouchRunSync()
        msg_match = "Neither `api_key` nor `api_key_env_var` have been provided."
        with pytest.raises(ValueError, match=msg_match):
            ht_task.run()

    def test_run_missing_api_key_with_api_key_env_var(self):
        ht_task = HightouchRunSync()
        msg_match = "We were unable to find the environment variable \\$foo."
        with pytest.raises(ValueError, match=msg_match):
            ht_task.run(api_key_env_var="foo")

    def test_run_missing_sync_id(self):
        ht_task = HightouchRunSync()
        msg_match = "`sync_id` has not been provided."
        with pytest.raises(ValueError, match=msg_match):
            ht_task.run(api_key="key")

    @responses.activate
    def test_run_with_api_key(self):
        ht_task = HightouchRunSync()
        sync_id = 123
        responses.add(
            responses.POST,
            f"https://api.hightouch.io/api/v2/rest/run/{sync_id}",
            status=200,
            json={"message": "it works"},
        )

        response = ht_task.run(api_key="key", sync_id=sync_id)

        assert responses.calls[0].request.headers["Authorization"] == "Bearer key"
        assert isinstance(response, dict)

    @patch.dict(os.environ, {"foo": "bar"})
    @responses.activate
    def test_run_with_api_key_env_var(self):
        ht_task = HightouchRunSync()
        sync_id = 123
        responses.add(
            responses.POST,
            f"https://api.hightouch.io/api/v2/rest/run/{sync_id}",
            status=200,
            json={"message": "it works"},
        )

        response = ht_task.run(api_key="key", sync_id=sync_id, api_key_env_var="foo")

        assert responses.calls[0].request.headers["Authorization"] == "Bearer key"
        assert isinstance(response, dict)

    @responses.activate
    def test_run_raises_on_status_code_not_ok(self):
        ht_task = HightouchRunSync()
        sync_id = 123
        responses.add(
            responses.POST,
            f"https://api.hightouch.io/api/v2/rest/run/{sync_id}",
            status=123,
        )

        msg = "Error while starting sync run."
        with pytest.raises(FAIL, match=msg):
            ht_task.run(api_key="key", sync_id=sync_id)

    @responses.activate
    def test_run_with_wait(self):
        ht_task = HightouchRunSync()
        sync_id = 123
        responses.add(
            responses.POST,
            f"https://api.hightouch.io/api/v2/rest/run/{sync_id}",
            status=200,
            json={"message": "it works"},
        )
        responses.add(
            responses.GET,
            f"https://api.hightouch.io/api/v2/rest/sync/{sync_id}",
            status=200,
            json={"sync": {"sync_status": "success"}},
        )

        response = ht_task.run(api_key="key", sync_id=123, wait_for_completion=True)

        responses.assert_call_count(
            f"https://api.hightouch.io/api/v2/rest/run/{sync_id}", 1
        )
        responses.assert_call_count(
            f"https://api.hightouch.io/api/v2/rest/sync/{sync_id}", 1
        )

        assert responses.calls[0].request.headers["Authorization"] == "Bearer key"
        assert isinstance(response, dict)
