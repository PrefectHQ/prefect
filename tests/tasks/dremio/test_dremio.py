import pytest
import os
from pyarrow.flight import FlightUnavailableError

from prefect.tasks.dremio.dremio import DremioFetch


class TestDremioFetch:
    def test_construction(self) -> None:
        task = DremioFetch(
            username="test_user", password="test_pass", hostname="test_host"
        )
        assert (task.username == "test_user") and (task.hostname == "test_host")

    def test_query_string_must_be_provided(self) -> None:
        task = DremioFetch(
            username="test_user", password="test_pass", hostname="test_host"
        )
        with pytest.raises(ValueError, match="A query string must be provided"):
            task.run()

    def test_wrong_client_returns_proper_error(self) -> None:
        task = DremioFetch()
        with pytest.raises(FlightUnavailableError):
            task.run(
                username="test_user",
                password="test_pass",
                hostname="test_host",
                tls=False,
                query="SELECT * FROM foo",
            )

    def test_no_query_client_returns_proper_error(self) -> None:
        task = DremioFetch()
        with pytest.raises(ValueError):
            task.run(
                username="test_user",
                password="test_pass",
                hostname="test_host",
                tls=False,
            )

    @pytest.mark.skipif(
        os.getenv("DREMIO_TEST_USER") is None,
        reason="You need env variables pointing to an actual Dremio cluster",
    )
    def test_fetch_on_actual_endpoint(self) -> None:
        task = DremioFetch(
            username=os.getenv("DREMIO_TEST_USER"),
            password=os.getenv("DREMIO_TEST_PASS"),
            hostname=os.getenv("DREMIO_TEST_HOST"),
            tls=True,
            certs=os.getenv("DREMIO_TEST_CERTS"),
        )
        result = task.run(query=os.getenv("DREMIO_TEST_QUERY"))
        assert isinstance(result, dict)
