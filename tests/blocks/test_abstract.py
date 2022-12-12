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

    def test_job_block_implementation(self):
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

            def fetch_results(self):
                if self.status != "completed":
                    raise JobRunIsRunning("Job run is still running.")
                return "results"

        class AJobBlock(JobBlock):
            def trigger(self):
                return AJobRun()

        a_job_block = AJobBlock()
        assert hasattr(a_job_block, "logger")

        a_job_run = a_job_block.trigger()
        assert hasattr(a_job_run, "logger")
        with pytest.raises(JobRunIsRunning, match="Job run is still running."):
            a_job_run.fetch_results()
        assert a_job_run.wait_for_completion() is None
        assert a_job_run.fetch_results() == "results"
