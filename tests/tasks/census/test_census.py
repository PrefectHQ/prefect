import pytest

from prefect.tasks.census import CensusSyncTask


class TestCensusSyncTask:
    def test_initializes_with_no_default(self):
        task = CensusSyncTask()
        assert task.api_trigger is None

    def test_run_failing_on_poor_url(self):
        task = CensusSyncTask(api_trigger="random_url.com")
        assert task.api_trigger == "random_url.com"
        with pytest.raises(ValueError, match="paste"):
            task.run()

    def test_improper_secret_failed(self):
        task = CensusSyncTask()
        with pytest.raises(ValueError, match="failed"):
            task.run(
                api_trigger="https://bearer:secret-token:BLAH@app.getcensus.com/api/v1/syncs/12/trigger"
            )
