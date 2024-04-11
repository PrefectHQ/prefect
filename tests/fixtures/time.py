from typing import Optional, Union

import pendulum
import pytest
from pendulum.tz.timezone import Timezone


@pytest.fixture
def frozen_time(monkeypatch: pytest.MonkeyPatch) -> pendulum.DateTime:
    frozen = pendulum.now("UTC")

    def frozen_time(tz: Optional[Union[str, Timezone]] = None):
        if tz is None:
            return frozen
        return frozen.in_timezone(tz)

    monkeypatch.setattr(pendulum, "now", frozen_time)
    return frozen
