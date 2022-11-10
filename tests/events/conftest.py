from uuid import uuid4

import pendulum
import pytest

from prefect.events.schemas import Event


@pytest.fixture
def example_event() -> Event:
    return Event(
        occurred=pendulum.now(),
        event="amazing.things.happened",
        resource={
            "prefect.resource.id": "a.cool.resource",
            "people": "shiny and happy",
            "lobsters": "rock",
        },
        related=[
            {
                "prefect.resource.id": "another.thing",
                "prefect.resource.role": "a-role",
                "hello": "world",
            },
            {
                "prefect.resource.id": "even.one.more.thing",
                "prefect.resource.role": "another-role",
                "goodnight": "moon",
            },
        ],
        payload={"it was": "awesome", "you're gonna": "love it"},
        id=uuid4(),
    )
