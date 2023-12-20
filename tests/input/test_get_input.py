import asyncio

import pytest

from prefect.context import FlowRunContext
from prefect.input import (
    InputWrapper,
    RunInput,
    filter_flow_run_input,
    get_input,
    send_input,
)


@pytest.fixture
def flow_run_context(flow_run, prefect_client):
    with FlowRunContext.construct(flow_run=flow_run, client=prefect_client) as context:
        yield context


class Person(RunInput):
    name: str
    email: str
    human: bool


async def test_send_input_stores_input(flow_run):
    person = Person(name="Bob", email="bob@bob.bob", human=True)
    await send_input(input=person, flow_run_id=flow_run.id)

    inputs = await filter_flow_run_input(
        key_prefix=person.keyset_from_type()["response"], flow_run_id=flow_run.id
    )

    assert len(inputs) == 1

    decoded = inputs[0].decoded_value
    value = decoded.pop("value")
    wrapper = InputWrapper(value=Person(**value), **decoded)

    assert wrapper.value == person


def test_send_input_stores_input_sync(flow_run):
    person = Person(name="Bob", email="bob@bob.bob", human=True)
    send_input(input=person, flow_run_id=flow_run.id)

    inputs = filter_flow_run_input(
        key_prefix=person.keyset_from_type()["response"], flow_run_id=flow_run.id
    )

    assert len(inputs) == 1

    decoded = inputs[0].decoded_value
    value = decoded.pop("value")
    wrapper = InputWrapper(value=Person(**value), **decoded)

    assert wrapper.value == person


async def test_send_input_infers_sender(flow_run_context):
    person = Person(name="Bob", email="bob@bob.bob", human=True)
    await send_input(input=person, flow_run_id=flow_run_context.flow_run.id)

    inputs = await filter_flow_run_input(
        key_prefix=person.keyset_from_type()["response"]
    )

    decoded = inputs[0].decoded_value
    value = decoded.pop("value")
    wrapper = InputWrapper(value=Person(**value), **decoded)

    # Since we're in a flow run context, the sender should be the flow run ID.
    # But since we're only dealing with a single flow run context here the
    # sender and receiver are the same.

    assert wrapper.sender == str(flow_run_context.flow_run.id)


async def test_send_input_can_set_sender(flow_run):
    person = Person(name="Bob", email="bob@bob.bob", human=True)
    await send_input(
        input=person,
        flow_run_id=flow_run.id,
        sender="sally",
    )

    inputs = await filter_flow_run_input(
        key_prefix=person.keyset_from_type()["response"], flow_run_id=flow_run.id
    )

    decoded = inputs[0].decoded_value
    value = decoded.pop("value")
    wrapper = InputWrapper(value=Person(**value), **decoded)

    assert wrapper.sender == "sally"


def test_get_input_works_sync(flow_run_context):
    person = Person(name="Bob", email="bob@example.com", human=True)
    send_input(
        input=person,
        flow_run_id=flow_run_context.flow_run.id,
    )

    received = get_input(Person).next()
    assert person == received


def test_get_input_wrapped_works_sync(flow_run_context):
    person = Person(name="Bob", email="bob@example.com", human=True)
    send_input(
        input=person,
        flow_run_id=flow_run_context.flow_run.id,
    )

    received = get_input(Person, wrapped=True).next()
    assert person == received.value


async def test_get_input_single_value(flow_run_context):
    person = Person(name="Bob", email="bob@example.com", human=True)
    await send_input(
        input=person,
        flow_run_id=flow_run_context.flow_run.id,
    )

    received = await get_input(Person).next()
    assert person == received


async def test_get_input_as_generator(flow_run_context):
    for name, email, human in [
        ("Bob", "bob@example.com", True),
        ("Sally", "sally@example.com", True),
        ("Bot", "bot@example.com", False),
    ]:
        person = Person(name=name, email=email, human=human)
        await send_input(
            input=person,
            flow_run_id=flow_run_context.flow_run.id,
        )

    received = []
    async for person in get_input(Person, timeout=0):
        received.append(person)

    assert len(received) == 3
    assert all(isinstance(person, Person) for person in received)
    assert {person.name for person in received} == {"Bob", "Sally", "Bot"}


async def test_get_input_single_wrapped_value(flow_run_context):
    person = Person(name="Bob", email="bob@example.com", human=True)
    await send_input(
        input=person,
        flow_run_id=flow_run_context.flow_run.id,
    )

    wrapper = await get_input(Person, wrapped=True).next()
    assert wrapper == InputWrapper(
        value=person, key=wrapper.key, sender=str(flow_run_context.flow_run.id)
    )


async def test_get_input_wrapped_as_generator(flow_run_context):
    for name, email, human in [
        ("Bob", "bob@example.com", True),
        ("Sally", "sally@example.com", True),
        ("Bot", "bot@example.com", False),
    ]:
        person = Person(name=name, email=email, human=human)
        await send_input(
            input=person,
            flow_run_id=flow_run_context.flow_run.id,
        )

    received = []
    async for wrapper in get_input(Person, timeout=0, wrapped=True):
        received.append(wrapper)

    assert len(received) == 3
    assert all(isinstance(wrapper, InputWrapper) for wrapper in received)
    assert {wrapper.value.name for wrapper in received} == {"Bob", "Sally", "Bot"}


async def test_get_input_waits_for_input(flow_run_context):
    async def send():
        # Sleep a bit to make sure that `receive` has started and failed to
        # find a matching input.
        await asyncio.sleep(0.5)
        await send_input(
            input=Person(name="Bob", email="bob@example.com", human=True),
            flow_run_id=flow_run_context.flow_run.id,
        )

    async def receive():
        person = await get_input(Person, timeout=1, poll_interval=0.1).next()
        return person

    _, received = await asyncio.gather(send(), receive())

    assert isinstance(received, Person)
    assert received.name == "Bob"


async def test_get_input_exclude_keys(flow_run_context):
    for name, email, human in [
        ("Bob", "bob@example.com", True),
        ("Sally", "sally@example.com", True),
        ("Bot", "bot@example.com", False),
    ]:
        person = Person(name=name, email=email, human=human)
        await send_input(
            input=person,
            flow_run_id=flow_run_context.flow_run.id,
        )

    # This is a bit contrived, but we want to make sure that we can exclude
    # certain keys from being returned by `get_input`. In this case, we're
    # going to get the first input, and then use get_input as a generator.
    # Without `exclude_keys` we would get the same input twice.
    excluded = await get_input(Person, wrapped=True).next()

    received = []
    async for person in get_input(Person, timeout=0, exclude_keys={excluded.key}):
        received.append(person)

    assert excluded not in received


async def test_get_input_generator_raise_timeout(flow_run_context):
    with pytest.raises(TimeoutError):
        async for item in get_input(
            Person, timeout=0.2, poll_interval=0.1, raise_timeout_error=True
        ):
            pass


def test_get_input_generator_raise_timeout_sync(flow_run_context):
    with pytest.raises(TimeoutError):
        for item in get_input(
            Person, timeout=0.2, poll_interval=0.1, raise_timeout_error=True
        ):
            pass


async def test_get_input_generator_no_raise_exits_gracefully(flow_run_context):
    async for item in get_input(Person, timeout=0.1):
        pass
    assert True


def test_get_input_generator_no_raise_exits_gracefully_sync(flow_run_context):
    for item in get_input(Person, timeout=0.1):
        pass
    assert True


async def test_get_input_generator_wrapped_raise_timeout(flow_run_context):
    with pytest.raises(TimeoutError):
        async for item in get_input(
            Person,
            timeout=0.2,
            poll_interval=0.1,
            raise_timeout_error=True,
            wrapped=True,
        ):
            pass


def test_get_input_generator_wrapped_raise_timeout_sync(flow_run_context):
    with pytest.raises(TimeoutError):
        for item in get_input(
            Person,
            timeout=0.1,
            poll_interval=0.2,
            raise_timeout_error=True,
            wrapped=True,
        ):
            pass


async def test_get_input_generator_wrapped_no_raise_exits_gracefully(flow_run_context):
    async for item in get_input(Person, timeout=0.1, wrapped=True):
        pass
    assert True


def test_get_input_generator_wrapped_no_raise_exits_gracefully_sync(flow_run_context):
    for item in get_input(Person, timeout=0.1, wrapped=True):
        pass
    assert True
