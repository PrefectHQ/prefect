from typing import Tuple
from uuid import uuid4

import orjson
import pytest

from prefect.client.schemas.objects import FlowRunInput
from prefect.context import FlowRunContext
from prefect.input import (
    RunInput,
)
from prefect.input.run_input import (
    receive_input,
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


class Place(RunInput):
    city: str
    state: str


def test_automatic_input_send_to_works_sync(flow_run):
    send_input(1, flow_run_id=flow_run.id)

    receive_iter = receive_input(int, flow_run_id=flow_run.id, timeout=0.1)
    received = receive_iter.next()
    assert received == 1


async def test_automatic_input_send_to_can_set_sender(flow_run):
    await send_input(1, flow_run_id=flow_run.id, sender="sally")

    received = await receive_input(
        int, flow_run_id=flow_run.id, timeout=0.1, with_metadata=True
    ).next()
    assert received.metadata.sender == "sally"


async def test_automatic_input_send_to_can_set_key_prefix(flow_run):
    await send_input(1, flow_run_id=flow_run.id, sender="sally", key_prefix="heythere")

    # Shouldn't work without the key prefix.
    with pytest.raises(TimeoutError):
        await receive_input(
            int, flow_run_id=flow_run.id, timeout=0.1, with_metadata=True
        ).next()

    # Now we should see it.
    received = await receive_input(
        int,
        flow_run_id=flow_run.id,
        timeout=0.1,
        with_metadata=True,
        key_prefix="heythere",
    ).next()
    assert received.metadata.sender == "sally"


async def test_send_to(flow_run):
    flow_run_input = FlowRunInput(
        flow_run_id=uuid4(),
        key="person-response",
        value=orjson.dumps(
            {"name": "Bob", "email": "bob@example.com", "human": True}
        ).decode(),
    )

    person = Person.load_from_flow_run_input(flow_run_input)
    await person.send_to(flow_run_id=flow_run.id)

    received = await Person.receive(flow_run_id=flow_run.id, timeout=0.1).next()
    assert isinstance(received, Person)
    assert person.name == "Bob"
    assert person.email == "bob@example.com"
    assert person.human is True


def test_send_to_works_sync(flow_run):
    flow_run_input = FlowRunInput(
        flow_run_id=uuid4(),
        key="person-response",
        value=orjson.dumps(
            {"name": "Bob", "email": "bob@example.com", "human": True}
        ).decode(),
    )

    person = Person.load_from_flow_run_input(flow_run_input)
    person.send_to(flow_run_id=flow_run.id)

    received = Person.receive(flow_run_id=flow_run.id, timeout=0.1).next()
    assert isinstance(received, Person)
    assert person.name == "Bob"
    assert person.email == "bob@example.com"
    assert person.human is True


async def test_send_to_can_set_sender(flow_run):
    flow_run_input = FlowRunInput(
        flow_run_id=uuid4(),
        key="person-response",
        value=orjson.dumps(
            {"name": "Bob", "email": "bob@example.com", "human": True}
        ).decode(),
    )

    person = Person.load_from_flow_run_input(flow_run_input)
    await person.send_to(flow_run_id=flow_run.id, sender="sally")

    received = await Person.receive(flow_run_id=flow_run.id, timeout=0.1).next()
    assert received.metadata.sender == "sally"


async def test_send_to_can_set_key_prefix(flow_run):
    flow_run_input = FlowRunInput(
        flow_run_id=uuid4(),
        key="person-response",
        value=orjson.dumps(
            {"name": "Bob", "email": "bob@example.com", "human": True}
        ).decode(),
    )

    person = Person.load_from_flow_run_input(flow_run_input)
    await person.send_to(flow_run_id=flow_run.id, key_prefix="heythere")

    received = await Person.receive(
        flow_run_id=flow_run.id, timeout=0.1, key_prefix="heythere"
    ).next()
    assert isinstance(received, Person)
    assert person.name == "Bob"
    assert person.email == "bob@example.com"
    assert person.human is True


async def test_automatic_input_can_receive_metadata(flow_run):
    await send_input(1, flow_run_id=flow_run.id)

    received = await receive_input(
        int, flow_run_id=flow_run.id, timeout=0.1, with_metadata=True
    ).next()
    assert received.value == 1


async def test_automatic_input_can_receive_without_metadata(flow_run):
    await send_input(1, flow_run_id=flow_run.id)

    received = await receive_input(int, flow_run_id=flow_run.id, timeout=0.1).next()
    assert received == 1


async def test_automatic_input_receive_multiple_values(flow_run):
    async def send():
        for city in [("New York", "NY"), ("Boston", "MA"), ("Chicago", "IL")]:
            await send_input(city, flow_run_id=flow_run.id)

    async def receive():
        received = []
        async for city in receive_input(
            Tuple[str, str], flow_run_id=flow_run.id, timeout=1, poll_interval=0.1
        ):
            received.append(city)
        return received

    await send()
    received = await receive()

    assert len(received) == 3
    assert all(isinstance(city, tuple) for city in received)
    assert set(received) == {
        ("New York", "NY"),
        ("Boston", "MA"),
        ("Chicago", "IL"),
    }


def test_automatic_input_receive_works_sync(flow_run):
    for city in [("New York", "NY"), ("Boston", "MA"), ("Chicago", "IL")]:
        send_input(city, flow_run_id=flow_run.id)

    received = []
    for city in receive_input(
        Tuple[str, str], flow_run_id=flow_run.id, timeout=5, poll_interval=0.1
    ):
        received.append(city)

    assert len(received) == 3
    assert all(isinstance(city, tuple) for city in received)
    assert set(received) == {
        ("New York", "NY"),
        ("Boston", "MA"),
        ("Chicago", "IL"),
    }


async def test_automatic_input_receive_with_exclude_keys(flow_run):
    for city in [("New York", "NY"), ("Boston", "MA"), ("Chicago", "IL")]:
        await send_input(city, flow_run_id=flow_run.id)

    # Receive the cities that were sent.
    received = []
    async for city in receive_input(
        Tuple[str, str], flow_run_id=flow_run.id, timeout=5, poll_interval=0.1
    ):
        received.append(city)
    assert len(received) == 3

    # Send a new city
    await send_input(("Los Angeles", "CA"), flow_run_id=flow_run.id)

    # Since this receive is being called without exclude_keys, it will receive
    # all of the cities that have been sent.
    received = []
    async for city in receive_input(
        Tuple[str, str],
        flow_run_id=flow_run.id,
        timeout=5,
        poll_interval=0.1,
        with_metadata=True,
    ):
        received.append(city)
    assert len(received) == 4

    # If we send another new city and receive excluding the keys that have
    # been previously received, we should only receive the new city.
    exclude_keys = {city.metadata.key for city in received}
    await send_input(("Portland", "OR"), flow_run_id=flow_run.id)
    received = []
    async for city in receive_input(
        Tuple[str, str], flow_run_id=flow_run.id, timeout=0, exclude_keys=exclude_keys
    ):
        received.append(city)

    assert len(received) == 1
    city = received[0]
    assert city[0] == "Portland"
    assert city[1] == "OR"


async def test_automatic_input_receive_can_can_raise_timeout_errors_as_generator(
    flow_run,
):
    with pytest.raises(TimeoutError):
        async for _ in receive_input(
            int,
            flow_run_id=flow_run.id,
            timeout=0,
            poll_interval=0.1,
            # Normally the loop would just exit, but this causes it to raise
            # when it doesn't receive a value for `timeout` seconds.
            raise_timeout_error=True,
        ):
            pass


def test_automatic_input_receive_can_can_raise_timeout_errors_as_generator_sync(
    flow_run,
):
    with pytest.raises(TimeoutError):
        for _ in receive_input(
            int,
            flow_run_id=flow_run.id,
            timeout=0,
            poll_interval=0.1,
            # Normally the loop would just exit, but this causes it to raise
            # when it doesn't receive a value for `timeout` seconds.
            raise_timeout_error=True,
        ):
            pass


async def test_automatic_input_receive_run_input_subclass(flow_run):
    await send_input(Place(city="New York", state="NY"), flow_run_id=flow_run.id)

    received = await receive_input(Place, flow_run_id=flow_run.id, timeout=0).next()
    assert received.city == "New York"
    assert received.state == "NY"


async def test_receive(flow_run):
    async def send():
        for city, state in [("New York", "NY"), ("Boston", "MA"), ("Chicago", "IL")]:
            await Place(city=city, state=state).send_to(flow_run_id=flow_run.id)

    async def receive():
        received = []
        async for place in Place.receive(
            flow_run_id=flow_run.id, timeout=1, poll_interval=0.1
        ):
            received.append(place)
        return received

    await send()
    received = await receive()

    assert len(received) == 3
    assert all(isinstance(place, Place) for place in received)
    assert {(place.city, place.state) for place in received} == {
        ("New York", "NY"),
        ("Boston", "MA"),
        ("Chicago", "IL"),
    }


def test_receive_works_sync(flow_run):
    for city, state in [("New York", "NY"), ("Boston", "MA"), ("Chicago", "IL")]:
        Place(city=city, state=state).send_to(flow_run_id=flow_run.id)

    received = []
    for place in Place.receive(flow_run_id=flow_run.id, timeout=5, poll_interval=0.1):
        received.append(place)

    assert len(received) == 3
    assert all(isinstance(place, Place) for place in received)
    assert {(place.city, place.state) for place in received} == {
        ("New York", "NY"),
        ("Boston", "MA"),
        ("Chicago", "IL"),
    }


async def test_receive_with_exclude_keys(flow_run):
    for city, state in [("New York", "NY"), ("Boston", "MA"), ("Chicago", "IL")]:
        await Place(city=city, state=state).send_to(flow_run_id=flow_run.id)

    # Receive the places that were sent.
    received = []
    async for place in Place.receive(flow_run_id=flow_run.id, timeout=0):
        received.append(place)
    assert len(received) == 3

    # Send a new place
    await Place(city="Los Angeles", state="CA").send_to(flow_run_id=flow_run.id)

    # Since this receive is being called without exclude_keys, it will receive
    # all of the places that have been sent.
    received = []
    async for place in Place.receive(flow_run_id=flow_run.id, timeout=0):
        received.append(place)
    assert len(received) == 4

    # Lets send another new place, and receive excluding the keys that have
    # been previously received and we should only receive the new place.
    exclude_keys = {place.metadata.key for place in received}
    await Place(city="Portland", state="OR").send_to(flow_run_id=flow_run.id)
    received = []
    async for place in Place.receive(
        flow_run_id=flow_run.id, timeout=0, exclude_keys=exclude_keys
    ):
        received.append(place)

    assert len(received) == 1
    place = received[0]
    assert place.city == "Portland"
    assert place.state == "OR"


async def test_receive_can_raise_timeout_errors_as_generator(flow_run):
    with pytest.raises(TimeoutError):
        async for _ in Place.receive(
            flow_run_id=flow_run.id,
            timeout=0,
            poll_interval=0.1,
            # Normally the loop would just exit, but this causes it to raise
            # when it doesn't receive a value for `timeout` seconds.
            raise_timeout_error=True,
        ):
            pass


def test_receive_can_raise_timeout_errors_as_generator_sync(flow_run):
    with pytest.raises(TimeoutError):
        for _ in Place.receive(
            flow_run_id=flow_run.id,
            timeout=0,
            poll_interval=0.1,
            # Normally the loop would just exit, but this causes it to raise
            # when it doesn't receive a value for `timeout` seconds.
            raise_timeout_error=True,
        ):
            pass
