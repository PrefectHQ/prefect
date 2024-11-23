from typing import List


def _validate_event_length(value: str) -> str:
    from prefect.settings import PREFECT_EVENTS_MAXIMUM_EVENT_NAME_LENGTH

    if len(value) > PREFECT_EVENTS_MAXIMUM_EVENT_NAME_LENGTH.value():
        raise ValueError(
            f"Event name must be at most {PREFECT_EVENTS_MAXIMUM_EVENT_NAME_LENGTH.value()} characters"
        )
    return value


def _validate_related_resources(value) -> List:
    from prefect.settings import PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES

    if len(value) > PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES.value():
        raise ValueError(
            "The maximum number of related resources "
            f"is {PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES.value()}"
        )
    return value
