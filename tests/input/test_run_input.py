import pydantic
import pytest

from prefect.context import FlowRunContext
from prefect.input import RunInput, create_flow_run_input, read_flow_run_input


@pytest.fixture
def flow_run_context(flow_run, prefect_client):
    with FlowRunContext.construct(flow_run=flow_run, client=prefect_client) as context:
        yield context


class Person(RunInput):
    name: str
    email: str
    human: bool


async def test_save_schema(flow_run_context):
    await Person.save(key="person")
    schema = await read_flow_run_input(key="person-schema")
    assert set(schema["properties"].keys()) == {
        "title",
        "description",
        "name",
        "email",
        "human",
    }


def test_save_works_sync(flow_run_context):
    Person.save(key="person")
    schema = read_flow_run_input(key="person-schema")
    assert set(schema["properties"].keys()) == {
        "title",
        "description",
        "name",
        "email",
        "human",
    }


async def test_save_explicit_flow_run(flow_run):
    await Person.save(key="person", flow_run_id=flow_run.id)
    schema = await read_flow_run_input(key="person-schema", flow_run_id=flow_run.id)
    assert schema is not None


async def test_save_key_suffix_override(flow_run):
    await Person.save(key="person", key_suffix="model", flow_run_id=flow_run.id)
    schema = await read_flow_run_input(key="person-model", flow_run_id=flow_run.id)
    assert schema is not None


async def test_load(flow_run_context):
    await create_flow_run_input(
        "person-response", value={"name": "Bob", "email": "bob@bob.bob", "human": True}
    )

    person = await Person.load(key="person")
    assert isinstance(person, Person)
    assert person.name == "Bob"
    assert person.email == "bob@bob.bob"
    assert person.human is True


def test_load_works_sync(flow_run_context):
    create_flow_run_input(
        "person-response", value={"name": "Bob", "email": "bob@bob.bob", "human": True}
    )

    person = Person.load(key="person")
    assert isinstance(person, Person)
    assert person.name == "Bob"
    assert person.email == "bob@bob.bob"
    assert person.human is True


async def test_load_explicit_flow_run(flow_run):
    await create_flow_run_input(
        "person-response",
        value={"name": "Bob", "email": "bob@bob.bob", "human": True},
        flow_run_id=flow_run.id,
    )

    person = await Person.load(key="person", flow_run_id=flow_run.id)
    assert isinstance(person, Person)


async def test_load_key_suffix_override(flow_run_context):
    await create_flow_run_input(
        "person-data", value={"name": "Bob", "email": "bob@bob.bob", "human": True}
    )

    person = await Person.load(key="person", key_suffix="data")
    assert isinstance(person, Person)


async def test_load_fails_validation_raises_exception(flow_run_context):
    await create_flow_run_input(
        "person-response",
        value={
            "name": "Bob",
            "email": "bob@bob.bob",
            "human": "123",
        },  # Human should be a boolean value.
    )

    with pytest.raises(pydantic.ValidationError, match="boolean"):
        person = await Person.load(key="person")
        assert isinstance(person, Person)


async def test_with_initial_data(flow_run_context):
    name = "Bob"
    new_cls = Person.with_initial_data(
        title=f"Fill in the missing data for {name}", name=name
    )

    await new_cls.save(key="person")
    schema = await read_flow_run_input(key="person-schema")
    assert (
        schema["properties"]["title"]["default"] == "Fill in the missing data for Bob"
    )
    assert schema["properties"]["name"]["default"] == "Bob"
