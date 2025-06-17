"""
Schema compatibility tests for LogCreate and Log types.

Tests the specific schema differences that caused the original bugs.
"""

from uuid import uuid4

from prefect.server.schemas.actions import LogCreate
from prefect.server.schemas.core import Log
from prefect.types._datetime import now

NOW = now("UTC")


class TestLogSchemaConversion:
    """Tests for LogCreate vs Log schema differences"""

    def test_logcreate_lacks_id_field(self):
        """Test that LogCreate doesn't have id field (this was causing the bug)"""
        log_create = LogCreate(
            name="test.logger",
            level=20,
            message="Test message",
            timestamp=NOW,
        )

        # LogCreate should NOT have id field (this was the issue)
        assert not hasattr(log_create, "id")

        # But Log should have id field
        log_full = Log(**log_create.model_dump())
        assert hasattr(log_full, "id")
        assert log_full.id is not None

    def test_logcreate_to_log_conversion(self):
        """Test converting LogCreate to Log preserves data and adds id"""
        log_create = LogCreate(
            name="test.logger",
            level=20,
            message="Test message",
            timestamp=NOW,
            flow_run_id=uuid4(),
            task_run_id=uuid4(),
        )

        # Convert LogCreate to Log (as done in create_logs)
        log_full = Log(**log_create.model_dump())

        # All LogCreate fields should be preserved
        assert log_full.name == log_create.name
        assert log_full.level == log_create.level
        assert log_full.message == log_create.message
        assert log_full.timestamp == log_create.timestamp
        assert log_full.flow_run_id == log_create.flow_run_id
        assert log_full.task_run_id == log_create.task_run_id

        # Log should have additional fields that LogCreate lacks
        assert log_full.id is not None  # This was missing from LogCreate
