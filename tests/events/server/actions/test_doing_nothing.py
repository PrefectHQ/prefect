import pytest

from prefect.server.events import actions
from prefect.server.events.schemas.automations import TriggeredAction


async def test_doing_nothing(
    caplog: pytest.LogCaptureFixture,
    email_me_when_that_dang_spider_comes: TriggeredAction,
):
    action = actions.DoNothing()

    with caplog.at_level("INFO"):
        await action.act(email_me_when_that_dang_spider_comes)

    assert "Doing nothing" in caplog.text
