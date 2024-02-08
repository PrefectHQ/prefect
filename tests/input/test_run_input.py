from uuid import uuid4

import orjson
import pydantic
import pytest

from prefect.client.schemas.objects import FlowRunInput
from prefect.context import FlowRunContext
from prefect.input import (
    RunInput,
    RunInputMetadata,
    create_flow_run_input,
    keyset_from_base_key,
    keyset_from_paused_state,
    read_flow_run_input,
)
from prefect.input.run_input import (
    AutomaticRunInput,
    receive_input,
    run_input_subclass_from_type,
    send_input,
)
from prefect.states import Paused, Running, Suspended


@pytest.fixture
def flow_run_context(flow_run, prefect_client):
    with FlowRunContext.construct(flow_run=flow_run, client=prefect_client) as context:
        yield context


class Person(RunInput):
    name: str
    email: str
    human: bool


class Place(RunInput):
    city: str
    state: str


def test_keyset_from_base_key():
    keyset = keyset_from_base_key("person")
    assert keyset["response"] == "person-response"
    assert keyset["schema"] == "person-schema"


def test_keyset_from_type():
    keyset = Person.keyset_from_type()
    assert keyset["response"] == "person-response"
    assert keyset["schema"] == "person-schema"


@pytest.mark.parametrize(
    "state,expected",
    [
        (Paused(pause_key="1"), keyset_from_base_key("paused-1")),
        (Suspended(pause_key="1"), keyset_from_base_key("suspended-1")),
    ],
)
def test_keyset_from_paused_state(state, expected):
    assert keyset_from_paused_state(state) == expected


def test_keyset_from_paused_state_non_paused_state_raises_exception():
    with pytest.raises(RuntimeError, match="unsupported"):
        keyset_from_paused_state(Running())


async def test_save_stores_schema(flow_run_context):
    keyset = keyset_from_base_key("person")
    await Person.save(keyset)
    schema = await read_flow_run_input(key=keyset["schema"])
    assert set(schema["properties"].keys()) == {
        "name",
        "email",
        "human",
    }


async def test_save_stores_provided_description(flow_run_context):
    keyset = keyset_from_base_key("person")
    await Person.with_initial_data(description="Testing").save(keyset)
    description = await read_flow_run_input(key=keyset["description"])
    assert description == "Testing"


def test_save_works_sync(flow_run_context):
    keyset = keyset_from_base_key("person")
    Person.save(keyset)
    schema = read_flow_run_input(key=keyset["schema"])
    assert set(schema["properties"].keys()) == {
        "name",
        "email",
        "human",
    }


async def test_save_explicit_flow_run(flow_run):
    keyset = keyset_from_base_key("person")
    await Person.save(keyset, flow_run_id=flow_run.id)
    schema = await read_flow_run_input(key=keyset["schema"], flow_run_id=flow_run.id)
    assert schema is not None


async def test_load(flow_run_context):
    keyset = keyset_from_base_key("person")
    await create_flow_run_input(
        keyset["response"],
        value={"name": "Bob", "email": "bob@bob.bob", "human": True},
    )

    person = await Person.load(keyset)
    assert isinstance(person, Person)
    assert person.name == "Bob"
    assert person.email == "bob@bob.bob"
    assert person.human is True


async def test_load_populates_metadata(flow_run_context):
    keyset = keyset_from_base_key("person")
    await create_flow_run_input(
        keyset["response"],
        value={"name": "Bob", "email": "bob@bob.bob", "human": True},
    )

    person = await Person.load(keyset)
    assert person.metadata == RunInputMetadata(
        key=keyset["response"], receiver=flow_run_context.flow_run.id, sender=None
    )


def test_load_works_sync(flow_run_context):
    keyset = keyset_from_base_key("person")
    create_flow_run_input(
        keyset["response"],
        value={"name": "Bob", "email": "bob@bob.bob", "human": True},
    )

    person = Person.load(keyset)
    assert isinstance(person, Person)
    assert person.name == "Bob"
    assert person.email == "bob@bob.bob"
    assert person.human is True


async def test_load_explicit_flow_run(flow_run):
    keyset = keyset_from_base_key("person")
    await create_flow_run_input(
        keyset["response"],
        value={"name": "Bob", "email": "bob@bob.bob", "human": True},
        flow_run_id=flow_run.id,
    )

    person = await Person.load(keyset, flow_run_id=flow_run.id)
    assert isinstance(person, Person)


async def test_load_fails_validation_raises_exception(flow_run_context):
    keyset = keyset_from_base_key("person")
    await create_flow_run_input(
        keyset["response"],
        value={
            "name": "Bob",
            "email": "bob@bob.bob",
            "human": "123",
        },  # Human should be a boolean value.
    )

    with pytest.raises(pydantic.ValidationError, match="boolean"):
        person = await Person.load(keyset)
        assert isinstance(person, Person)


async def test_load_from_flow_run_input(flow_run_context):
    flow_run_input = FlowRunInput(
        flow_run_id=flow_run_context.flow_run.id,
        key="person-response",
        value=orjson.dumps(
            {"name": "Bob", "email": "bob@example.com", "human": True}
        ).decode(),
        sender=f"prefect.flow-run.{uuid4()}",
    )

    person = Person.load_from_flow_run_input(flow_run_input)

    assert person.name == "Bob"
    assert person.email == "bob@example.com"
    assert person.human is True
    assert person.metadata == RunInputMetadata(
        key=flow_run_input.key,
        receiver=flow_run_context.flow_run.id,
        sender=flow_run_input.sender,
    )


async def test_with_initial_data(flow_run_context):
    keyset = keyset_from_base_key("bob")

    name = "Bob"
    new_cls = Person.with_initial_data(name=name)

    await new_cls.save(keyset)
    schema = await read_flow_run_input(key=keyset["schema"])
    assert schema["properties"]["name"]["default"] == "Bob"


async def test_run_input_from_type_str(flow_run_context):
    new_cls = run_input_subclass_from_type(str)
    assert issubclass(new_cls, AutomaticRunInput)
    obj = new_cls(value="hey")
    assert obj.value == "hey"


async def test_run_input_from_type_basemodel(flow_run_context):
    class MyModel(pydantic.BaseModel):
        name: str
        age: int

    new_cls = run_input_subclass_from_type(MyModel)
    assert issubclass(new_cls, RunInput)
    obj = new_cls(name="Bob", age=42)
    assert obj.name == "Bob"
    assert obj.age == 42


async def test_respond(flow_run):
    flow_run_input = FlowRunInput(
        flow_run_id=uuid4(),
        key="person-response",
        value=orjson.dumps(
            {"name": "Bob", "email": "bob@example.com", "human": True}
        ).decode(),
        sender=f"prefect.flow-run.{flow_run.id}",
    )

    person = Person.load_from_flow_run_input(flow_run_input)
    await person.respond(Place(city="New York", state="NY"))

    place = await Place.receive(flow_run_id=flow_run.id, timeout=0.1).next()
    assert isinstance(place, Place)
    assert place.city == "New York"
    assert place.state == "NY"


def test_respond_functions_sync(flow_run):
    flow_run_input = FlowRunInput(
        flow_run_id=uuid4(),
        key="person-response",
        value=orjson.dumps(
            {"name": "Bob", "email": "bob@example.com", "human": True}
        ).decode(),
        sender=f"prefect.flow-run.{flow_run.id}",
    )

    person = Person.load_from_flow_run_input(flow_run_input)
    person.respond(Place(city="New York", state="NY"))

    place = Place.receive(flow_run_id=flow_run.id, timeout=0.1).next()
    assert isinstance(place, Place)
    assert place.city == "New York"
    assert place.state == "NY"


async def test_respond_can_set_sender(flow_run):
    flow_run_input = FlowRunInput(
        flow_run_id=uuid4(),
        key="person-response",
        value=orjson.dumps(
            {"name": "Bob", "email": "bob@example.com", "human": True}
        ).decode(),
        sender=f"prefect.flow-run.{flow_run.id}",
    )

    person = Person.load_from_flow_run_input(flow_run_input)
    await person.respond(Place(city="New York", state="NY"), sender="sally")

    place = await Place.receive(flow_run_id=flow_run.id, timeout=0.1).next()
    assert place.metadata.sender == "sally"


async def test_respond_can_set_key_prefix(flow_run):
    flow_run_input = FlowRunInput(
        flow_run_id=uuid4(),
        key="person-response",
        value=orjson.dumps(
            {"name": "Bob", "email": "bob@example.com", "human": True}
        ).decode(),
        sender=f"prefect.flow-run.{flow_run.id}",
    )

    person = Person.load_from_flow_run_input(flow_run_input)
    await person.respond(Place(city="New York", state="NY"), key_prefix="heythere")

    place = await Place.receive(
        flow_run_id=flow_run.id, timeout=0.1, key_prefix="heythere"
    ).next()
    assert isinstance(place, Place)
    assert place.city == "New York"
    assert place.state == "NY"


async def test_respond_raises_exception_no_sender_in_input():
    flow_run_input = FlowRunInput(
        flow_run_id=uuid4(),
        key="person-response",
        value=orjson.dumps(
            {"name": "Bob", "email": "bob@example.com", "human": True}
        ).decode(),
        sender=None,
    )

    person = Person.load_from_flow_run_input(flow_run_input)

    with pytest.raises(RuntimeError, match="Cannot respond"):
        await person.respond(Place(city="New York", state="NY"))


async def test_respond_uses_automatic_input_if_needed(flow_run):
    flow_run_input = FlowRunInput(
        flow_run_id=uuid4(),
        key="person-response",
        value=orjson.dumps(
            {"name": "Bob", "email": "bob@example.com", "human": True}
        ).decode(),
        sender=f"prefect.flow-run.{flow_run.id}",
    )

    person = Person.load_from_flow_run_input(flow_run_input)
    await person.respond("hey")

    message = await receive_input(str, flow_run_id=flow_run.id).next()
    assert isinstance(message, str)
    assert message == "hey"


async def test_automatic_input_send_to(flow_run):
    await send_input(1, flow_run_id=flow_run.id)

    received = await receive_input(int, flow_run_id=flow_run.id, timeout=0.1).next()
    assert received == 1
