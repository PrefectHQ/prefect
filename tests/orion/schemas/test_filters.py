from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa

from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.schemas.filters import LogFilter


NOW = datetime.now()


async def test_filters_without_params_do_not_error():
    class MyFilter(schemas.filters.PrefectFilterBaseModel):
        def _get_filter_list(self):
            return []

    # should not error
    MyFilter().as_sql_filter()


class TestLogFilters:
    @inject_db
    def test_applies_level_filter(self, db):
        log_filter = LogFilter(level={"any_": [10]})
        sql_filter = log_filter.as_sql_filter()
        assert sql_filter.compare(sa.and_(db.Log.level.in_([10])))

    @inject_db
    def test_applies_timestamp_filter_before(self, db):
        log_filter = LogFilter(timestamp={"before_": NOW})
        sql_filter = log_filter.as_sql_filter()
        assert sql_filter.compare(sa.and_(db.Log.timestamp <= NOW))

    @inject_db
    def test_applies_timestamp_filter_after(self, db):
        log_filter = LogFilter(timestamp={"after_": NOW})
        sql_filter = log_filter.as_sql_filter()
        assert sql_filter.compare(sa.and_(db.Log.timestamp >= NOW))

    def test_applies_flow_run_id_filter(self, db):
        flow_run_id = uuid4()
        log_filter = LogFilter(flow_run_id={"any_": [flow_run_id]})
        sql_filter = log_filter.as_sql_filter()
        assert sql_filter.compare(sa.and_(db.Log.flow_run_id.in_([flow_run_id])))

    def test_applies_task_run_id_filter(self, db):
        task_run_id = uuid4()
        log_filter = LogFilter(task_run_id={"any_": [task_run_id]})
        sql_filter = log_filter.as_sql_filter()
        assert sql_filter.compare(sa.and_(db.Log.task_run_id.in_([task_run_id])))

    def test_applies_multiple_conditions(self, db):
        task_run_id = uuid4()
        log_filter = LogFilter(
            task_run_id={"any_": [task_run_id]}, level={"any_": [20, 50]}
        )
        sql_filter = log_filter.as_sql_filter()
        assert sql_filter.compare(
            sa.and_(db.Log.task_run_id.in_([task_run_id]), db.Log.level.in_([20, 50]))
        )
