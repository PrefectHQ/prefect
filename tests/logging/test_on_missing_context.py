"""Tests for the on_missing_context parameter of get_run_logger."""

import logging

import pytest

from prefect.exceptions import MissingContextError
from prefect.logging.loggers import get_run_logger


class TestOnMissingContext:
    """Tests for the on_missing_context parameter."""

    def test_raise_is_default_behavior(self):
        """Default behavior raises MissingContextError outside a run context."""
        with pytest.raises(
            MissingContextError, match="no active flow or task run context"
        ):
            get_run_logger()

    def test_raise_explicit(self):
        """Explicitly passing on_missing_context='raise' raises MissingContextError."""
        with pytest.raises(
            MissingContextError, match="no active flow or task run context"
        ):
            get_run_logger(on_missing_context="raise")

    def test_raise_mentions_on_missing_context(self):
        """MissingContextError message mentions on_missing_context kwarg."""
        with pytest.raises(MissingContextError, match="on_missing_context"):
            get_run_logger()

    def test_warn_returns_logger(self):
        """on_missing_context='warn' returns a fallback logger instead of raising."""
        logger = get_run_logger(on_missing_context="warn")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "prefect"

    def test_warn_emits_debug_message(self, caplog):
        """on_missing_context='warn' emits a debug message about the fallback."""
        with caplog.at_level(logging.DEBUG, logger="prefect"):
            get_run_logger(on_missing_context="warn")
        assert any(
            "No active flow or task run context found" in record.message
            for record in caplog.records
        )

    def test_ignore_returns_logger(self):
        """on_missing_context='ignore' returns a fallback logger silently."""
        logger = get_run_logger(on_missing_context="ignore")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "prefect"

    def test_ignore_does_not_emit_message(self, caplog):
        """on_missing_context='ignore' does not emit any log messages."""
        with caplog.at_level(logging.DEBUG, logger="prefect"):
            get_run_logger(on_missing_context="ignore")
        assert not any(
            "No active flow or task run context found" in record.message
            for record in caplog.records
        )

    def test_fallback_logger_is_functional(self):
        """The fallback logger can actually log messages."""
        logger = get_run_logger(on_missing_context="ignore")
        # Should not raise
        logger.info("test message from fallback logger")
        logger.warning("test warning from fallback logger")

    def test_custom_fallback_logger_name_warn(self):
        """fallback_logger_name controls the logger name in warn mode."""
        logger = get_run_logger(
            on_missing_context="warn", fallback_logger_name="my_app"
        )
        assert isinstance(logger, logging.Logger)
        assert logger.name == "prefect.my_app"

    def test_custom_fallback_logger_name_ignore(self):
        """fallback_logger_name controls the logger name in ignore mode."""
        logger = get_run_logger(
            on_missing_context="ignore", fallback_logger_name="my_app"
        )
        assert isinstance(logger, logging.Logger)
        assert logger.name == "prefect.my_app"
