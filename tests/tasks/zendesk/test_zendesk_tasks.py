from prefect.tasks import zendesk
from prefect.tasks.zendesk import ZendeskTicketsIncrementalExportTask


class TestZendeskTasks:

    def test_construciton_zendesk_tickets_incremental_export_no_values(self):
        zendesk_task = ZendeskTicketsIncrementalExportTask()

        assert zendesk_task.subdomain is None
        assert zendesk_task.api_token is None
        assert zendesk_task.api_token_env_var is None
        assert zendesk_task.email_address is None
        assert zendesk_task.start_time is None
        assert zendesk_task.cursor is None
        assert zendesk_task.exclude_deleted is None
        assert zendesk_task.include_entities is None