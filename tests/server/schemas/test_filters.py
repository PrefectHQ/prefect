from uuid import uuid4

import pendulum
import sqlalchemy as sa

from prefect.server import schemas
from prefect.server.schemas.filters import LogFilter

NOW = pendulum.now()


async def test_filters_without_params_do_not_error():
    class MyFilter(schemas.filters.PrefectFilterBaseModel):
        def _get_filter_list(self, db):
            return []

    # should not error
    MyFilter().as_sql_filter(None)


class TestLogFilters:
    def test_applies_level_le_filter(self, db):
        log_filter = LogFilter(level={"le_": 10})
        sql_filter = log_filter.as_sql_filter(db)
        assert sql_filter.compare(sa.and_(db.Log.level <= 10))

    def test_applies_level_ge_filter(self, db):
        log_filter = LogFilter(level={"ge_": 10})
        sql_filter = log_filter.as_sql_filter(db)
        assert sql_filter.compare(sa.and_(db.Log.level >= 10))

    def test_applies_timestamp_filter_before(self, db):
        log_filter = LogFilter(timestamp={"before_": NOW})
        sql_filter = log_filter.as_sql_filter(db)
        assert sql_filter.compare(sa.and_(db.Log.timestamp <= NOW))

    def test_applies_timestamp_filter_after(self, db):
        log_filter = LogFilter(timestamp={"after_": NOW})
        sql_filter = log_filter.as_sql_filter(db)
        assert sql_filter.compare(sa.and_(db.Log.timestamp >= NOW))

    def test_applies_flow_run_id_filter(self, db):
        flow_run_id = uuid4()
        log_filter = LogFilter(flow_run_id={"any_": [flow_run_id]})
        sql_filter = log_filter.as_sql_filter(db)
        assert sql_filter.compare(sa.and_(db.Log.flow_run_id.in_([flow_run_id])))

    def test_applies_task_run_id_filter(self, db):
        task_run_id = uuid4()
        log_filter = LogFilter(task_run_id={"any_": [task_run_id]})
        sql_filter = log_filter.as_sql_filter(db)
        assert sql_filter.compare(sa.and_(db.Log.task_run_id.in_([task_run_id])))

    def test_applies_multiple_conditions(self, db):
        task_run_id = uuid4()
        log_filter = LogFilter(task_run_id={"any_": [task_run_id]}, level={"ge_": 20})
        sql_filter = log_filter.as_sql_filter(db)
        assert sql_filter.compare(
            sa.and_(db.Log.task_run_id.in_([task_run_id]), db.Log.level >= 20)
        )
