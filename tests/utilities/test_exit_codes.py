import logging

import pytest

from prefect.utilities._infrastructure_exit_codes import (
    INFRASTRUCTURE_EXIT_HINTS,
    InfrastructureExitInfo,
    get_infrastructure_exit_info,
)


class TestInfrastructureExitInfo:
    def test_default_log_level_is_error(self):
        info = InfrastructureExitInfo(explanation="test", resolution="test")
        assert info.log_level == logging.ERROR

    def test_is_frozen(self):
        info = InfrastructureExitInfo(explanation="a", resolution="b")
        with pytest.raises(AttributeError):
            info.explanation = "c"  # type: ignore[misc]


class TestInfrastructureExitHints:
    @pytest.mark.parametrize(
        "code", [0, -9, -15, 1, 125, 126, 127, 137, 143, 247, 0xC000013A]
    )
    def test_known_codes_present(self, code: int):
        assert code in INFRASTRUCTURE_EXIT_HINTS

    def test_code_zero_is_info_level(self):
        assert INFRASTRUCTURE_EXIT_HINTS[0].log_level == logging.INFO

    @pytest.mark.parametrize("code", [-9, -15, 143, 0xC000013A])
    def test_signal_codes_are_info_level(self, code: int):
        assert INFRASTRUCTURE_EXIT_HINTS[code].log_level == logging.INFO

    @pytest.mark.parametrize("code", [1, 125, 126, 127, 137, 247])
    def test_error_codes_are_error_level(self, code: int):
        assert INFRASTRUCTURE_EXIT_HINTS[code].log_level == logging.ERROR


class TestGetInfrastructureExitInfo:
    def test_known_code_returns_registry_entry(self):
        info = get_infrastructure_exit_info(137)
        assert info is INFRASTRUCTURE_EXIT_HINTS[137]

    def test_unknown_code_returns_generic_entry(self):
        info = get_infrastructure_exit_info(42)
        assert "unexpected" in info.explanation
        assert info.log_level == logging.ERROR

    def test_zero_returns_clean_exit(self):
        info = get_infrastructure_exit_info(0)
        assert info.log_level == logging.INFO
        assert "cleanly" in info.explanation

    def test_negative_unknown_code(self):
        info = get_infrastructure_exit_info(-99)
        assert "unexpected" in info.explanation
