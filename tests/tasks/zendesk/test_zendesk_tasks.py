import logging
from re import sub

import pytest
from prefect.engine.signals import FAIL
from prefect.tasks.zendesk import ZendeskTicketsIncrementalExportTask

import responses


class TestZendeskTasks:
    def test_construciton_zendesk_tickets_incremental_export_no_values(self):
        zendesk_task = ZendeskTicketsIncrementalExportTask()

        assert zendesk_task.subdomain is None
        assert zendesk_task.api_token is None
        assert zendesk_task.api_token_env_var is None
        assert zendesk_task.email_address is None
        assert zendesk_task.start_time is None
        assert zendesk_task.cursor is None
        assert zendesk_task.exclude_deleted is False
        assert zendesk_task.include_entities is None

    def test_construction_zendesk_tickets_incremental_export_with_values(self):
        zendesk_task = ZendeskTicketsIncrementalExportTask(
            subdomain="foo",
            email_address="foo@bar.com",
            api_token="secret",
            api_token_env_var="secret_env_var",
            start_time=123,
            cursor="abc",
            exclude_deleted=True,
            include_entities=["a", "b"],
        )

        assert zendesk_task.subdomain == "foo"
        assert zendesk_task.email_address == "foo@bar.com"
        assert zendesk_task.api_token == "secret"
        assert zendesk_task.api_token_env_var == "secret_env_var"
        assert zendesk_task.start_time == 123
        assert zendesk_task.cursor == "abc"
        assert zendesk_task.exclude_deleted is True
        assert zendesk_task.include_entities == ["a", "b"]

    def test_run_without_api_token_and_api_token_env_var_raises(self):
        zendesk_task = ZendeskTicketsIncrementalExportTask()
        with pytest.raises(ValueError) as exc:
            zendesk_task.run()

        assert "Both `api_token` and `api_token_env_var` are missing." in str(exc)

    def test_run_without_api_token_and_missing_api_token_env_var_raises(self):
        zendesk_task = ZendeskTicketsIncrementalExportTask(api_token_env_var="abc")
        with pytest.raises(ValueError) as exc:
            zendesk_task.run()

        assert "`api_token` is missing and `api_token_env_var` not found." in str(exc)

    def test_run_without_subdomain_raises(self):
        zendesk_task = ZendeskTicketsIncrementalExportTask()
        with pytest.raises(ValueError) as exc:
            zendesk_task.run(api_token="abc")

        assert "`subdomain` is missing." in str(exc)

    def test_run_without_email_address_raises(self):
        zendesk_task = ZendeskTicketsIncrementalExportTask()
        with pytest.raises(ValueError) as exc:
            zendesk_task.run(api_token="abc", subdomain="foo")

        assert "`email_address` is missing." in str(exc)

    def test_run_without_start_time_and_cursor_raises(self):
        zendesk_task = ZendeskTicketsIncrementalExportTask()
        with pytest.raises(ValueError) as exc:
            zendesk_task.run(
                api_token="abc", subdomain="foo", email_address="foo@bar.com"
            )

        assert "Both `start_time` and `cursor` are missing." in str(exc)

    @responses.activate
    def test_run_with_cursor(self, caplog):
        caplog.set_level(logging.DEBUG)
        zendesk_task = ZendeskTicketsIncrementalExportTask()
        responses.add(
            responses.GET,
            url="https://test.zendesk.com/api/v2/cursor.json?cursor=xyz",
            json={
                "end_of_stream": True,
                "after_url": "foo",
                "after_cursor": "foo",
                "tickets": [],
            },
            headers={"retry-after": "1"},
            status=200,
        )

        zendesk_task.run(
            subdomain="test", email_address="foo@bar.com", api_token="abc", cursor="xyz"
        )

        assert "Got cursor" in caplog.text

    @responses.activate
    def test_run_with_start_time(self, caplog):
        caplog.set_level(logging.DEBUG)
        zendesk_task = ZendeskTicketsIncrementalExportTask()
        responses.add(
            responses.GET,
            url="https://test.zendesk.com/api/v2/cursor.json?start_time=123",
            json={
                "end_of_stream": True,
                "after_url": "foo",
                "after_cursor": "foo",
                "tickets": [],
            },
            headers={"retry-after": "1"},
            status=200,
        )

        zendesk_task.run(
            subdomain="test",
            email_address="foo@bar.com",
            api_token="abc",
            start_time=123,
        )

        assert "Got start_time" in caplog.text

    @responses.activate
    def test_run_retry_after(self, caplog):
        caplog.set_level(logging.DEBUG)
        zendesk_task = ZendeskTicketsIncrementalExportTask()
        responses.add(
            responses.GET,
            url="https://test.zendesk.com/api/v2/cursor.json?start_time=123",
            json={
                "end_of_stream": False,
                "after_url": "foo",
                "after_cursor": "foo",
                "tickets": [],
            },
            headers={"retry-after": "1"},
            status=429,
        )

        responses.add(
            responses.GET,
            url="https://test.zendesk.com/api/v2/cursor.json?start_time=123",
            json={
                "end_of_stream": True,
                "after_url": "foo",
                "after_cursor": "foo",
                "tickets": [],
            },
            headers={"retry-after": "1"},
            status=200,
        )

        zendesk_task.run(
            subdomain="test",
            email_address="foo@bar.com",
            api_token="abc",
            start_time=123,
        )

        assert "API rate limit reached!" in caplog.text

    @responses.activate
    def test_run_api_call_fail_raises(self):
        zendesk_task = ZendeskTicketsIncrementalExportTask()
        responses.add(
            responses.GET,
            url="https://test.zendesk.com/api/v2/cursor.json?start_time=123",
            json={
                "end_of_stream": False,
                "after_url": "foo",
                "after_cursor": "foo",
                "tickets": [],
            },
            headers={"retry-after": "1"},
            status=123,
        )

        with pytest.raises(FAIL) as exc:
            zendesk_task.run(
                subdomain="test",
                email_address="foo@bar.com",
                api_token="abc",
                start_time=123,
            )

        assert "Zendesk API call failed!" in str(exc)

    @responses.activate
    def test_run_success(self):
        zendesk_task = ZendeskTicketsIncrementalExportTask()
        responses.add(
            responses.GET,
            url="https://test.zendesk.com/api/v2/cursor.json?start_time=123",
            json={
                "end_of_stream": True,
                "after_url": "foo",
                "after_cursor": "foo",
                "tickets": [{"ticket_id": 1, "ticket_desc": "bar"}],
            },
            headers={"retry-after": "1"},
            status=200,
        )

        tickets = zendesk_task.run(
            subdomain="test",
            email_address="foo@bar.com",
            api_token="abc",
            start_time=123,
        )

        assert isinstance(tickets["tickets"], list)
        assert {"ticket_id": 1, "ticket_desc": "bar"} in tickets["tickets"]
    
    @responses.activate
    def test_run_success_with_include_entities(self):
        zendesk_task = ZendeskTicketsIncrementalExportTask()
        responses.add(
            responses.GET,
            url="https://test.zendesk.com/api/v2/cursor.json?start_time=123&include=bar,foo",
            json={
                "end_of_stream": True,
                "after_url": "foo",
                "after_cursor": "foo",
                "tickets": [{"ticket_id": 1, "ticket_desc": "bar"}],
                "foo": [{"key": "value"}],
                "bar": [{"key": "value"}]
            },
            headers={"retry-after": "1"},
            status=200,
        )

        tickets = zendesk_task.run(
            subdomain="test",
            email_address="foo@bar.com",
            api_token="abc",
            start_time=123,
            include_entities=["foo", "foo", "bar"]
        )

        assert isinstance(tickets["tickets"], list)
        assert {"ticket_id": 1, "ticket_desc": "bar"} in tickets["tickets"]

        assert isinstance(tickets["foo"], list)
        assert {"key": "value"} in tickets["foo"]

        assert isinstance(tickets["bar"], list)
        assert {"key": "value"} in tickets["bar"]
