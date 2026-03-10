"""Tests for the raise_on_lease_renewal_failure parameter."""

from contextlib import contextmanager
from unittest import mock
from uuid import uuid4

from prefect.concurrency._sync import concurrency


@contextmanager
def mock_concurrency_internals(*, limits_exist: bool = True):
    """Mock the internal concurrency APIs for testing parameter plumbing."""
    mock_response = mock.MagicMock()
    if limits_exist:
        mock_response.limits = [mock.MagicMock()]
        mock_response.lease_id = uuid4()
    else:
        mock_response.limits = []

    with (
        mock.patch(
            "prefect.concurrency._sync.acquire_concurrency_slots_with_lease",
            return_value=mock_response,
        ),
        mock.patch(
            "prefect.concurrency._sync.release_concurrency_slots_with_lease",
        ),
        mock.patch(
            "prefect.concurrency._sync.emit_concurrency_acquisition_events",
            return_value={},
        ),
        mock.patch(
            "prefect.concurrency._sync.emit_concurrency_release_events",
        ),
        mock.patch(
            "prefect.concurrency._sync.maintain_concurrency_lease",
        ) as mock_maintain,
    ):
        mock_maintain.return_value.__enter__ = mock.MagicMock()
        mock_maintain.return_value.__exit__ = mock.MagicMock(return_value=False)
        yield mock_maintain


class TestRaiseOnLeaseRenewalFailure:
    """Tests for the raise_on_lease_renewal_failure parameter."""

    def test_defaults_to_strict_when_not_set(self):
        """When raise_on_lease_renewal_failure is None, it follows strict."""
        with mock_concurrency_internals() as mock_maintain:
            with concurrency(["test"], occupy=1, strict=True):
                pass
            mock_maintain.assert_called_once()
            assert (
                mock_maintain.call_args.kwargs["raise_on_lease_renewal_failure"] is True
            )

    def test_defaults_to_non_strict_when_not_set(self):
        """When raise_on_lease_renewal_failure is None and strict=False, renewal is non-strict."""
        with mock_concurrency_internals() as mock_maintain:
            with concurrency(["test"], occupy=1, strict=False):
                pass
            mock_maintain.assert_called_once()
            assert (
                mock_maintain.call_args.kwargs["raise_on_lease_renewal_failure"]
                is False
            )

    def test_explicit_false_overrides_strict(self):
        """raise_on_lease_renewal_failure=False with strict=True gives strict acquisition + non-fatal renewal."""
        with mock_concurrency_internals() as mock_maintain:
            with concurrency(
                ["test"], occupy=1, strict=True, raise_on_lease_renewal_failure=False
            ):
                pass
            mock_maintain.assert_called_once()
            assert (
                mock_maintain.call_args.kwargs["raise_on_lease_renewal_failure"]
                is False
            )

    def test_explicit_true_overrides_non_strict(self):
        """raise_on_lease_renewal_failure=True with strict=False gives non-strict acquisition + fatal renewal."""
        with mock_concurrency_internals() as mock_maintain:
            with concurrency(
                ["test"], occupy=1, strict=False, raise_on_lease_renewal_failure=True
            ):
                pass
            mock_maintain.assert_called_once()
            assert (
                mock_maintain.call_args.kwargs["raise_on_lease_renewal_failure"] is True
            )

    def test_skips_lease_maintenance_when_no_limits(self):
        """When no limits exist and strict=False, lease maintenance is not called."""
        with mock_concurrency_internals(limits_exist=False) as mock_maintain:
            with concurrency(["test"], occupy=1, strict=False):
                pass
            mock_maintain.assert_not_called()
