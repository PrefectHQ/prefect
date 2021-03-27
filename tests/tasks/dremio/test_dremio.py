import pytest
from pyarrow.flight import FlightUnavailableError

from prefect.tasks.dremio.dremio import DremioFetch


class TestDremioFetch:
    def test_construction(self) -> None:
        task = DremioFetch(user="test", password="test", host="test")
        assert (task.user == "test") and (task.host == "test")

    def test_query_string_must_be_provided(self) -> None:
        task = DremioFetch(user="test", password="test", host="test")
        with pytest.raises(ValueError, match="A query string must be provided"):
            task.run()

    def test_wrong_client_returns_proper_error(self) -> None:
        task = DremioFetch(user="test", password="test", host="test")
        with pytest.raises(FlightUnavailableError):
            task.run(query="SELECT * FROM foo")
