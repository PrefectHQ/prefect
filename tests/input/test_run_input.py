import pydantic
import pytest

from prefect.context import FlowRunContext
from prefect.input import (
    RunInput,
    create_flow_run_input,
    keyset_from_base_key,
    keyset_from_paused_state,
    read_flow_run_input,
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


def test_keyset_from_base_key():
    keyset = keyset_from_base_key("person")
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


async def test_save_schema(flow_run_context):
    keyset = keyset_from_base_key("person")
    await Person.save(keyset)
    schema = await read_flow_run_input(key=keyset["schema"])
    assert set(schema["properties"].keys()) == {
        "title",
        "description",
        "name",
        "email",
        "human",
    }


def test_save_works_sync(flow_run_context):
    keyset = keyset_from_base_key("person")
    Person.save(keyset)
    schema = read_flow_run_input(key=keyset["schema"])
    assert set(schema["properties"].keys()) == {
        "title",
        "description",
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


async def test_with_initial_data(flow_run_context):
    keyset = keyset_from_base_key("bob")

    name = "Bob"
    new_cls = Person.with_initial_data(
        title=f"Fill in the missing data for {name}", name=name
    )

    await new_cls.save(keyset)
    schema = await read_flow_run_input(key=keyset["schema"])
    assert (
        schema["properties"]["title"]["default"] == "Fill in the missing data for Bob"
    )
    assert schema["properties"]["name"]["default"] == "Bob"
