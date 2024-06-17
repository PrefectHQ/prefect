from base64 import b64decode, b64encode
import json
from typing import TYPE_CHECKING, List, Optional, Tuple
from prefect.server.events.counting import TimeUnit
from prefect.server.events.schemas.events import EventCount


if TYPE_CHECKING:  # pragma: no cover
    from prefect.server.events.filters import EventFilter


INTERACTIVE_PAGE_SIZE: int = 50


class InvalidTokenError(ValueError):
    pass


def to_page_token(
    filter: "EventFilter", count: int, page_size: int, current_offset: int
) -> Optional[str]:
    if current_offset + page_size >= count:
        return None

    return b64encode(
        json.dumps(
            {
                "filter": filter.model_dump(mode="json"),
                "count": count,
                "page_size": page_size,
                "offset": current_offset + page_size,
            }
        ).encode()
    ).decode()


def from_page_token(page_token: str) -> Tuple["EventFilter", int, int, int]:
    from prefect.server.events.filters import EventFilter

    try:
        parameters = json.loads(b64decode(page_token))
    except Exception:
        # If we can't parse the page token, this likely indicates that something was
        # wrong with the query parameters (perhaps truncated or otherwise manipulated).
        # Treat this as a request for nothing
        raise InvalidTokenError("Unable to parse page token")

    return (
        EventFilter.model_validate(parameters["filter"]),
        parameters["count"],
        parameters["page_size"],
        parameters["offset"],
    )


def process_time_based_counts(
    filter: "EventFilter",
    time_unit: TimeUnit,
    time_interval: float,
    counts: List[EventCount],
) -> List[EventCount]:
    """
    Common logic for processing time-based counts across different event backends.

    When doing time-based counting we want to do two things:

    1. Backfill any missing intervals with 0 counts.
    2. Update the start/end times that are emitted to match the beginning and
    end of the intervals rather than having them reflect the true max/min
    occurred time of the events themselves.
    """

    span_generator = time_unit.get_interval_spans(
        filter.occurred.since, filter.occurred.until, time_interval
    )

    spans_since_pivot = next(span_generator)
    assert isinstance(spans_since_pivot, int)

    backfilled_counts = [
        EventCount(
            value=str(i),
            count=0,
            label=start_time.isoformat(),
            start_time=start_time,
            end_time=end_time,
        )
        for i, (start_time, end_time) in enumerate(span_generator)
    ]

    for count in counts:
        index = int(float(count.value)) - spans_since_pivot
        backfilled_counts[index].count = count.count

    return backfilled_counts


class QueryRangeTooLarge(Exception):
    pass
