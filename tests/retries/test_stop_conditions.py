import pytest

from prefect.retries._dataclasses import AttemptState, Phase
from prefect.retries.stop_conditions import (
    AttemptsExhausted,
    ExceptionMatches,
    IntersectionStopCondition,
    NoException,
    UnionStopCondition,
)


class TestStopCondition:
    def test_eq(self):
        stop_condition = AttemptsExhausted(3)
        assert stop_condition == AttemptsExhausted(3)
        assert stop_condition != AttemptsExhausted(4)
        assert stop_condition != NoException()
        assert stop_condition != 3


class TestAttemptsExhausted:
    def test_attempts_exhausted(self):
        stop_condition = AttemptsExhausted(3)
        assert stop_condition.is_met(None) is False

        context = AttemptState(attempt=1, phase=Phase.FAILED)
        context.exception = RuntimeError()
        assert stop_condition.is_met(context) is False

        context = AttemptState(attempt=2, phase=Phase.FAILED)
        context.exception = RuntimeError()
        assert stop_condition.is_met(context) is False

        context = AttemptState(attempt=3, phase=Phase.FAILED)
        context.exception = RuntimeError()
        assert stop_condition.is_met(context) is True

    def test_invalid_max_attempts(self):
        with pytest.raises(ValueError):
            AttemptsExhausted(0)

        with pytest.raises(ValueError):
            AttemptsExhausted(-1)


class TestNoException:
    def test_no_exception(self):
        stop_condition = NoException()
        assert stop_condition.is_met(None) is False

        context = AttemptState(attempt=1, phase=Phase.FAILED)
        context.exception = RuntimeError()
        assert stop_condition.is_met(context) is False


class TestExceptionMatches:
    def test_exception_matches(self):
        stop_condition = ExceptionMatches(RuntimeError)
        assert stop_condition.is_met(None) is False

        context = AttemptState(attempt=1, phase=Phase.FAILED)
        context.exception = RuntimeError()
        assert stop_condition.is_met(context) is True


class TestIntersectionStopCondition:
    def test_all_conditions_met(self):
        context = AttemptState(attempt=3, phase=Phase.FAILED)
        context.exception = RuntimeError()
        stop_condition = IntersectionStopCondition(AttemptsExhausted(3), NoException())
        assert stop_condition.is_met(context) is False  # NoException not met
        context.exception = None
        context.phase = Phase.SUCCEEDED
        assert stop_condition.is_met(context) is True  # Both met

    def test_not_all_conditions_met(self):
        context = AttemptState(attempt=2, phase=Phase.FAILED)
        context.exception = RuntimeError()
        stop_condition = IntersectionStopCondition(AttemptsExhausted(3), NoException())
        assert stop_condition.is_met(context) is False

    def test_creation_via_and(self):
        # A bit nonsensical, but we'll test it anyway.
        stop_condition = AttemptsExhausted(3) & NoException()
        assert isinstance(stop_condition, IntersectionStopCondition)

        # No exception, but the max attempts is not reached, so it should be false.
        context = AttemptState(attempt=1, phase=Phase.SUCCEEDED)
        assert stop_condition.is_met(context) is False

        # Max attempts is reached, but there is an exception, so it should be false.
        context = AttemptState(attempt=3, phase=Phase.FAILED)
        context.exception = RuntimeError()
        assert stop_condition.is_met(context) is False

        # No exception and the max attempts is reached, so it should be true.
        context = AttemptState(attempt=3, phase=Phase.SUCCEEDED)
        context.exception = None
        assert stop_condition.is_met(context) is True


class TestUnionStopCondition:
    def test_any_condition_met(self):
        context = AttemptState(attempt=3, phase=Phase.FAILED)
        context.exception = RuntimeError()
        stop_condition = UnionStopCondition(AttemptsExhausted(3), NoException())
        assert stop_condition.is_met(context) is True  # AttemptsExhausted met
        context = AttemptState(attempt=1, phase=Phase.SUCCEEDED)
        context.exception = None
        assert stop_condition.is_met(context) is True  # NoException met

    def test_no_conditions_met(self):
        context = AttemptState(attempt=1, phase=Phase.FAILED)
        context.exception = RuntimeError()
        stop_condition = UnionStopCondition(AttemptsExhausted(3), NoException())
        assert stop_condition.is_met(context) is False

    def test_creation_via_or(self):
        stop_condition = AttemptsExhausted(3) | NoException()
        assert isinstance(stop_condition, UnionStopCondition)

        # No exception, so it should be true.
        context = AttemptState(attempt=1, phase=Phase.SUCCEEDED)
        assert stop_condition.is_met(context) is True

        # Max attempts is reached, so it should be true.
        context = AttemptState(attempt=3, phase=Phase.FAILED)
        context.exception = RuntimeError()
        assert stop_condition.is_met(context) is True


class TestComplexStopConditionCombinations:
    def test_nested_and_or(self):
        # (AttemptsExhausted(3) & NoException()) | ExceptionMatches(ValueError)
        stop_condition = (AttemptsExhausted(3) & NoException()) | ExceptionMatches(
            ValueError
        )
        context = AttemptState(attempt=1, phase=Phase.FAILED)
        context.exception = RuntimeError()
        assert (
            stop_condition.is_met(context) is False
        )  # Neither AND nor ExceptionMatches(ValueError) met

        context = AttemptState(attempt=3, phase=Phase.FAILED)
        context.exception = RuntimeError()
        assert (
            stop_condition.is_met(context) is False
        )  # AND not met, ExceptionMatches(ValueError) not met

        context.exception = None
        context.phase = Phase.SUCCEEDED
        assert stop_condition.is_met(context) is True  # AND met

        context = AttemptState(attempt=1, phase=Phase.FAILED)
        context.exception = ValueError()
        assert (
            stop_condition.is_met(context) is True
        )  # ExceptionMatches(ValueError) met

    def test_nested_or_and(self):
        # (AttemptsExhausted(3) | NoException()) & ExceptionMatches(ValueError)
        stop_condition = (AttemptsExhausted(3) | NoException()) & ExceptionMatches(
            ValueError
        )
        context = AttemptState(attempt=1, phase=Phase.FAILED)
        context.exception = RuntimeError()
        assert (
            stop_condition.is_met(context) is False
        )  # ExceptionMatches(ValueError) not met

        context.exception = ValueError()
        assert (
            stop_condition.is_met(context) is False
        )  # ExceptionMatches(ValueError) met, NoException not met

        context = AttemptState(attempt=3, phase=Phase.FAILED)
        context.exception = ValueError()
        assert (
            stop_condition.is_met(context) is True
        )  # AttemptsExhausted(3) met, ExceptionMatches(ValueError) met

    def test_multiple_and_or(self):
        # AttemptsExhausted(3) & NoException() & ExceptionMatches(ValueError)
        stop_condition = (
            AttemptsExhausted(3) & NoException() & ExceptionMatches(ValueError)
        )
        context = AttemptState(attempt=3, phase=Phase.FAILED)
        context.exception = ValueError()
        assert stop_condition.is_met(context) is False  # NoException not met

        context.exception = None
        context.phase = Phase.SUCCEEDED
        assert (
            stop_condition.is_met(context) is False
        )  # ExceptionMatches(ValueError) not met

    def test_multiple_or(self):
        # AttemptsExhausted(3) | NoException() | ExceptionMatches(ValueError)
        stop_condition = (
            AttemptsExhausted(3) | NoException() | ExceptionMatches(ValueError)
        )
        context = AttemptState(attempt=1, phase=Phase.FAILED)
        context.exception = RuntimeError()
        assert stop_condition.is_met(context) is False

        context = AttemptState(attempt=3, phase=Phase.FAILED)
        context.exception = RuntimeError()
        assert stop_condition.is_met(context) is True  # AttemptsExhausted(3) met

        context = AttemptState(attempt=1, phase=Phase.SUCCEEDED)
        context.exception = None
        assert stop_condition.is_met(context) is True  # NoException met

        context = AttemptState(attempt=1, phase=Phase.FAILED)
        context.exception = ValueError()
        assert (
            stop_condition.is_met(context) is True
        )  # ExceptionMatches(ValueError) met


class TestInvertedStopCondition:
    def test_inverted_stop_condition(self):
        stop_condition = ~ExceptionMatches(RuntimeError)
        assert stop_condition.is_met(None) is False

        context = AttemptState(attempt=1, phase=Phase.FAILED)
        context.exception = RuntimeError()
        assert stop_condition.is_met(context) is False

        context = AttemptState(attempt=1, phase=Phase.FAILED)
        context.exception = ValueError()
        assert stop_condition.is_met(context) is True

    def test_double_inversion(self):
        original_stop_condition = ExceptionMatches(RuntimeError)
        inverted_stop_condition = ~original_stop_condition
        assert ~inverted_stop_condition is original_stop_condition
        assert ~original_stop_condition == inverted_stop_condition
