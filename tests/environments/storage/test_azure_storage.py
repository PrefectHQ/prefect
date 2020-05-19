from unittest.mock import MagicMock

import cloudpickle
import pytest

from prefect import Flow
from prefect.environments.storage import Azure

pytest.importorskip("azure.storage.blob")


def test_create_azure_storage():
    storage = Azure(container="test")
    assert storage
    assert storage.logger


def test_create_azure_storage_init_args():
    storage = Azure(
        container="test", connection_string="conn", blob_name="name", secrets=["foo"],
    )
    assert storage
    assert storage.flows == dict()
    assert storage.container == "test"
    assert storage.connection_string == "conn"
    assert storage.blob_name == "name"
    assert storage.secrets == ["foo"]


def test_serialize_azure_storage():
    storage = Azure(container="test")
    serialized_storage = storage.serialize()

    assert serialized_storage["type"] == "Azure"


def test_blob_service_client_property(monkeypatch):
    connection = MagicMock()
    azure = MagicMock(from_connection_string=connection)
    monkeypatch.setattr("azure.storage.blob.BlobServiceClient", azure)

    storage = Azure(container="test", connection_string="conn")

    azure_client = storage._azure_block_blob_service
    assert azure_client
    connection.assert_called_with(conn_str="conn")


def test_add_flow_to_azure():
    storage = Azure(container="test")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f)
    assert f.name in storage


def test_add_multiple_flows_to_Azure():
    storage = Azure(container="container")

    f = Flow("test")
    g = Flow("testg")
    assert f.name not in storage
    assert storage.add_flow(f)
    assert storage.add_flow(g)
    assert f.name in storage
    assert g.name in storage


def test_upload_flow_to_azure(monkeypatch):
    client = MagicMock(upload_blob=MagicMock())
    service = MagicMock(get_blob_client=MagicMock(return_value=client))
    monkeypatch.setattr(
        "prefect.environments.storage.Azure._azure_block_blob_service", service
    )

    storage = Azure(container="container")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f)
    assert storage.build()
    assert client.upload_blob.called
    assert f.name in storage


def test_upload_flow_to_azure_blob_name(monkeypatch):
    client = MagicMock(upload_blob=MagicMock())
    service = MagicMock(get_blob_client=MagicMock(return_value=client))
    monkeypatch.setattr(
        "prefect.environments.storage.Azure._azure_block_blob_service", service
    )

    storage = Azure(container="container", blob_name="name")

    f = Flow("test")
    assert storage.add_flow(f)
    assert storage.build()

    assert service.get_blob_client.call_args[1]["container"] == "container"
    assert service.get_blob_client.call_args[1]["blob"] == "name"


def test_upload_multiple_flows_to_azure_blob_name(monkeypatch):
    client = MagicMock(upload_blob=MagicMock())
    service = MagicMock(get_blob_client=MagicMock(return_value=client))
    monkeypatch.setattr(
        "prefect.environments.storage.Azure._azure_block_blob_service", service
    )

    storage = Azure(container="container", blob_name="name")

    f1 = Flow("test1")
    f2 = Flow("test2")
    assert storage.add_flow(f1)
    assert storage.add_flow(f2)
    assert storage.build()

    assert service.get_blob_client.call_args[1]["container"] == "container"


def test_upload_flow_to_azure_blob_name_format(monkeypatch):
    client = MagicMock(upload_blob=MagicMock())
    service = MagicMock(get_blob_client=MagicMock(return_value=client))
    monkeypatch.setattr(
        "prefect.environments.storage.Azure._azure_block_blob_service", service
    )

    storage = Azure(container="container")

    f = Flow("test")
    assert storage.add_flow(f)
    assert storage.build()

    assert service.get_blob_client.call_args[1]["container"] == "container"
    key = service.get_blob_client.call_args[1]["blob"].split("/")

    assert key[0] == "test"
    assert key[1]


def test_add_flow_to_azure_already_added(monkeypatch):
    storage = Azure(container="container")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f)
    assert f.name in storage

    with pytest.raises(ValueError):
        storage.add_flow(f)


def test_get_flow_azure(monkeypatch):
    client = MagicMock(download_blob=MagicMock())
    service = MagicMock(get_blob_client=MagicMock(return_value=client))
    monkeypatch.setattr(
        "prefect.environments.storage.Azure._azure_block_blob_service", service
    )

    f = Flow("test")

    monkeypatch.setattr("cloudpickle.loads", MagicMock(return_value=f))

    storage = Azure(container="container")

    assert f.name not in storage
    flow_location = storage.add_flow(f)

    assert storage.get_flow(flow_location)
    assert client.download_blob.called
    assert f.name in storage


def test_get_flow_azure_bucket_key(monkeypatch):
    client = MagicMock(download_blob=MagicMock())
    service = MagicMock(get_blob_client=MagicMock(return_value=client))
    monkeypatch.setattr(
        "prefect.environments.storage.Azure._azure_block_blob_service", service
    )

    f = Flow("test")

    monkeypatch.setattr("cloudpickle.loads", MagicMock(return_value=f))

    storage = Azure(container="container", blob_name="name")

    assert f.name not in storage
    flow_location = storage.add_flow(f)

    assert storage.get_flow(flow_location)
    assert service.get_blob_client.call_args[1]["container"] == "container"
    assert service.get_blob_client.call_args[1]["blob"] == flow_location


def test_get_flow_azure_runs(monkeypatch):
    client = MagicMock(download_blob=MagicMock())
    service = MagicMock(get_blob_client=MagicMock(return_value=client))
    monkeypatch.setattr(
        "prefect.environments.storage.Azure._azure_block_blob_service", service
    )

    f = Flow("test")

    monkeypatch.setattr("cloudpickle.loads", MagicMock(return_value=f))

    storage = Azure(container="container")

    assert f.name not in storage
    flow_location = storage.add_flow(f)

    new_flow = storage.get_flow(flow_location)
    assert client.download_blob.called
    assert f.name in storage

    assert isinstance(new_flow, Flow)
    assert new_flow.name == "test"
    assert len(new_flow.tasks) == 0

    state = new_flow.run()
    assert state.is_successful()
