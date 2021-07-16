from prefect.core.utilites import file_hash


def test_file_hash_returns_hash():
    assert isinstance(file_hash(__file__), str)
