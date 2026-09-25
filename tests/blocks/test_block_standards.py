from io import BytesIO
from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError

import pytest

from prefect.blocks.core import Block
from prefect.testing.standard_test_suites import BlockStandardTestSuite
from prefect.testing.standard_test_suites import blocks as standard_blocks
from prefect.utilities.dispatch import get_registry_for_type
from prefect.utilities.importtools import to_qualified_name

block_registry = get_registry_for_type(Block) or {}

blocks_under_test = [
    block
    for block in block_registry.values()
    if to_qualified_name(block).startswith("prefect.")
]


@pytest.mark.parametrize(
    "block", sorted(blocks_under_test, key=lambda x: x.get_block_type_slug())
)
class TestAllBlocksAdhereToStandards(BlockStandardTestSuite):
    @pytest.fixture
    def block(self, block):
        return block


class TestFetchLogo:
    @pytest.fixture(autouse=True)
    def no_sleep(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(standard_blocks.time, "sleep", lambda _: None)

    @staticmethod
    def _response(data: bytes) -> MagicMock:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = data
        return response

    def test_succeeds_after_transient_error(self, monkeypatch: pytest.MonkeyPatch):
        urlopen = MagicMock(
            side_effect=[
                HTTPError("u", 402, "Payment Required", None, None),  # type: ignore[arg-type]
                self._response(b"img"),
            ]
        )
        monkeypatch.setattr(standard_blocks, "urlopen", urlopen)

        result = standard_blocks._fetch_logo("u")

        assert isinstance(result, BytesIO)
        assert result.getvalue() == b"img"
        assert urlopen.call_count == 2

    @pytest.mark.parametrize(
        "error",
        [
            HTTPError("u", 402, "Payment Required", None, None),  # type: ignore[arg-type]
            HTTPError("u", 503, "Unavailable", None, None),  # type: ignore[arg-type]
            URLError(TimeoutError("timed out")),
            TimeoutError("timed out"),
        ],
    )
    def test_skips_when_cdn_stays_unavailable(
        self, monkeypatch: pytest.MonkeyPatch, error: Exception
    ):
        urlopen = MagicMock(side_effect=error)
        monkeypatch.setattr(standard_blocks, "urlopen", urlopen)

        with pytest.raises(pytest.skip.Exception, match="Logo CDN unavailable"):
            standard_blocks._fetch_logo("u", attempts=3)

        assert urlopen.call_count == 3

    @pytest.mark.parametrize(
        "error",
        [
            HTTPError("u", 404, "Not Found", None, None),  # type: ignore[arg-type]
            HTTPError("u", 403, "Forbidden", None, None),  # type: ignore[arg-type]
            URLError(OSError("Name or service not known")),
        ],
    )
    def test_raises_immediately_for_broken_urls(
        self, monkeypatch: pytest.MonkeyPatch, error: Exception
    ):
        urlopen = MagicMock(side_effect=error)
        monkeypatch.setattr(standard_blocks, "urlopen", urlopen)

        with pytest.raises(type(error)):
            standard_blocks._fetch_logo("u")

        assert urlopen.call_count == 1
