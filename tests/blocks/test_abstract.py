import pytest

from prefect.blocks.abstract import JobBlock, JobRun
from prefect.exceptions import PrefectException


class JobRunIsRunning(PrefectException):
    """Raised when a job run is still running."""


class TestJobBlock:
    def test_job_block_is_abstract(self):
        with pytest.raises(
            TypeError, match="Can't instantiate abstract class JobBlock"
        ):
            JobBlock()

    def test_job_block_implementation(self, caplog):
        class AJobRun(JobRun):
            def __init__(self):
                self.status = "running"

            @property
            def status(self):
                return self._status

            @status.setter
            def status(self, value):
                self._status = value

            def wait_for_completion(self):
                self.status = "completed"
                self.logger.info("Job run completed.")

            def fetch_result(self):
                if self.status != "completed":
                    raise JobRunIsRunning("Job run is still running.")
                return "results"

        class AJobBlock(JobBlock):
            def trigger(self):
                self.logger.info("Job run triggered.")
                return AJobRun()

        a_job_block = AJobBlock()
        a_job_run = a_job_block.trigger()

        # test wait_for_completion and fetch_result
        with pytest.raises(JobRunIsRunning, match="Job run is still running."):
            a_job_run.fetch_result()
        assert a_job_run.wait_for_completion() is None
        assert a_job_run.fetch_result() == "results"

        # test logging
        assert hasattr(a_job_block, "logger")
        assert hasattr(a_job_run, "logger")
        assert len(caplog.records) == 2
        record_1 = caplog.records[0]
        assert record_1.name == "prefect.AJobBlock"
        assert record_1.msg == "Job run triggered."
        record_2 = caplog.records[1]
        assert record_2.name == "prefect.AJobRun"
        assert record_2.msg == "Job run completed."
