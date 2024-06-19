from prefect_sqlalchemy.credentials import ConnectionComponents, SyncDriver
from pydantic import SecretStr
from sqlalchemy.engine.url import make_url


def test_sqlalchemy_connection_components_create_url_minimal():
    connection_components = ConnectionComponents(
        driver=SyncDriver.POSTGRESQL_PSYCOPG2, database="my.db"
    )
    actual = connection_components.create_url()
    assert actual == make_url("postgresql+psycopg2:///my.db")


def test_sqlalchemy_connection_components_create_url_optional_params():
    connection_components = ConnectionComponents(
        driver=SyncDriver.POSTGRESQL_PSYCOPG2,
        database="my.db",
        username="myusername",
        password=SecretStr("mypass"),
        port=1234,
        host="localhost",
    )
    actual = connection_components.create_url()
    assert actual == make_url(
        "postgresql+psycopg2://myusername:mypass@localhost:1234/my.db"
    )
