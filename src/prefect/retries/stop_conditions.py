from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prefect.retries._dataclasses import AttemptState


class StopCondition(abc.ABC):
    """
    A protocol that defines a stopping condition for an attempting generator.
    """

    @abc.abstractmethod
    def is_met(self, context: AttemptState | None) -> bool:
        """
        Checks if execution should stop.

        Args:
            context: The current attempt context.

        Returns:
            True if the stopping condition is met, False otherwise.
        """
        ...  # pragma: no cover

    def __and__(self, other: StopCondition) -> StopCondition:
        return IntersectionStopCondition(self, other)

    def __or__(self, other: StopCondition) -> StopCondition:
        return UnionStopCondition(self, other)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StopCondition):
            return False
        return self.__dict__ == other.__dict__

    def __invert__(self) -> StopCondition:
        return InvertedStopCondition(self)


class NoException(StopCondition):
    """
    A StopCondition implementation that stops if no exception is raised in the attempt
    context.
    """

    def is_met(self, context: AttemptState | None) -> bool:
        if context is None:
            return False
        return context.exception is None


class ExceptionMatches(StopCondition):
    """
    A StopCondition implementation that stops if the exception matches the given type.
    """

    def __init__(self, exception_type: type[BaseException]):
        self.exception_type = exception_type

    def is_met(self, context: AttemptState | None) -> bool:
        if context is None:
            return False
        return isinstance(context.exception, self.exception_type)


class AttemptsExhausted(StopCondition):
    """
    A StopCondition implementation that stops after a fixed number of attempts.

    Attributes:
        max_attempts: The maximum number of attempts. Execution will stop after
            this many failed attempts.
    """

    def __init__(self, max_attempts: int):
        if max_attempts <= 0:
            raise ValueError("max_attempts must be greater than 0")
        self.max_attempts = max_attempts

    def is_met(self, context: AttemptState | None) -> bool:
        if context is None:
            return False
        return context.attempt >= self.max_attempts


class IntersectionStopCondition(StopCondition):
    """
    A StopCondition implementation that stops if all of the given StopCondition
    instances are met.
    """

    def __init__(self, *conditions: StopCondition):
        self.conditions: tuple[StopCondition, ...] = conditions

    def is_met(self, context: AttemptState | None) -> bool:
        return all(condition.is_met(context) for condition in self.conditions)


class UnionStopCondition(StopCondition):
    """
    A StopCondition implementation that stops if any of the given StopCondition
    instances are met.
    """

    def __init__(self, *conditions: StopCondition):
        self.conditions: tuple[StopCondition, ...] = conditions

    def is_met(self, context: AttemptState | None) -> bool:
        return any(condition.is_met(context) for condition in self.conditions)


class InvertedStopCondition(StopCondition):
    """
    A StopCondition implementation that inverts the given StopCondition.
    """

    def __init__(self, condition: StopCondition):
        self.condition = condition

    def is_met(self, context: AttemptState | None) -> bool:
        if context is None:
            return False
        return not self.condition.is_met(context)

    def __invert__(self) -> StopCondition:
        return self.condition


__all__ = [
    "AttemptsExhausted",
    "ExceptionMatches",
    "IntersectionStopCondition",
    "NoException",
    "StopCondition",
    "UnionStopCondition",
]
