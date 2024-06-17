from datetime import timedelta

import pytest

from prefect.server.events.schemas.automations import (
    CompoundTrigger,
    EventTrigger,
    Posture,
)


async def test_compound_trigger_requires_too_small():
    with pytest.raises(ValueError, match="require must be at least 1"):
        CompoundTrigger(
            triggers=[
                EventTrigger(
                    expect={"dragon.seen"},
                    match={
                        "color": "red",
                    },
                    posture=Posture.Reactive,
                    threshold=1,
                ),
                EventTrigger(
                    expect={"dragon.seen"},
                    match={
                        "color": "green",
                    },
                    posture=Posture.Reactive,
                    threshold=1,
                ),
            ],
            require=0,
            within=timedelta(seconds=10),
        )


async def test_compound_trigger_requires_too_big():
    with pytest.raises(
        ValueError,
        match="require must be less than or equal to the number of triggers",
    ):
        CompoundTrigger(
            triggers=[
                EventTrigger(
                    expect={"dragon.seen"},
                    match={
                        "color": "red",
                    },
                    posture=Posture.Reactive,
                    threshold=1,
                ),
                EventTrigger(
                    expect={"dragon.seen"},
                    match={
                        "color": "green",
                    },
                    posture=Posture.Reactive,
                    threshold=1,
                ),
            ],
            require=3,
            within=timedelta(seconds=10),
        )
