from prefect.core.orion.client import set_client, get_client, Client


def test_get_client_creates_default():
    client = get_client()
    assert isinstance(client, Client)


def test_set_client():
    client = Client()
    set_client(client)
    assert get_client() is client
