from prefect.environments import storage


def test_default_storage():
    assert storage.get_default_storage_class() is storage.Docker
