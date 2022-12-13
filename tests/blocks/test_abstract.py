import pytest

from prefect.blocks.abstract import DatabaseBlock, JobBlock, JobRun
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


class TestDatabaseBlock:
    def test_database_block_is_abstract(self):
        with pytest.raises(
            TypeError, match="Can't instantiate abstract class DatabaseBlock"
        ):
            DatabaseBlock()

    async def test_database_block_implementation(self, caplog):
        class ADatabaseBlock(DatabaseBlock):
            def __init__(self):
                self._results = tuple(
                    zip(["apple", "banana", "cherry"], [1, 2, 3], [True, False, True])
                )
                self._engine = None

            def fetch_one(self, operation, parameters=None, **execution_kwargs):
                self.logger.info(f"Fetching one result using {parameters}.")
                return self._results[0]

            def fetch_many(
                self, operation, parameters=None, size=None, **execution_kwargs
            ):
                self.logger.info(f"Fetching {size} results using {parameters}.")
                return self._results[:size]

            def fetch_all(self, operation, parameters=None, **execution_kwargs):
                self.logger.info(f"Fetching all results using {parameters}.")
                return self._results

            def execute(self, operation, parameters=None, **execution_kwargs) -> None:
                self.logger.info(f"Executing operation using {parameters}.")

            def execute_many(
                self, operation, seq_of_parameters, **execution_kwargs
            ) -> None:
                self.logger.info(
                    f"Executing many operations using {seq_of_parameters}."
                )

            def __enter__(self):
                self._engine = True
                return self

            def __exit__(self, *args):
                self._engine = None

        a_database_block = ADatabaseBlock()
        parameters = {"a": "b"}
        assert a_database_block.fetch_one(
            "SELECT * FROM table", parameters=parameters
        ) == ("apple", 1, True)
        assert a_database_block.fetch_many(
            "SELECT * FROM table", size=2, parameters=parameters
        ) == (("apple", 1, True), ("banana", 2, False))
        assert a_database_block.fetch_all(
            "SELECT * FROM table", parameters=parameters
        ) == (("apple", 1, True), ("banana", 2, False), ("cherry", 3, True))
        assert (
            a_database_block.execute(
                "INSERT INTO table VALUES (1, 2, 3)", parameters=parameters
            )
            is None
        )
        assert (
            a_database_block.execute_many(
                "INSERT INTO table VALUES (1, 2, 3)",
                seq_of_parameters=[parameters, parameters],
                parameters=parameters,
            )
            is None
        )

        records = caplog.records
        for record in records:
            assert record.name == "prefect.ADatabaseBlock"
        assert records[0].message == "Fetching one result using {'a': 'b'}."
        assert records[1].message == "Fetching 2 results using {'a': 'b'}."
        assert records[2].message == "Fetching all results using {'a': 'b'}."
        assert records[3].message == "Executing operation using {'a': 'b'}."
        assert (
            records[4].message
            == "Executing many operations using [{'a': 'b'}, {'a': 'b'}]."
        )

        # test context manager
        with a_database_block as db:
            assert db._engine is True
        assert a_database_block._engine is None

        match = "ADatabaseBlock does not support async context management."
        with pytest.raises(NotImplementedError, match=match):
            async with a_database_block:
                pass
