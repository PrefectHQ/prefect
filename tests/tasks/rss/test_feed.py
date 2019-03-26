
from unittest.mock import MagicMock

import pytest

from prefect.tasks.rss import ParseRSSFeed

class TestParseRSSFeedTask:
    def test_empty_initialization(self):
        task = ParseRSSFeed()
        assert not task.feed_url

    def test_filled_initialization(self):
        task = ParseRSSFeed(feed_url="test")
        assert task.feed_url == "test"

    def test_empty_feed_url_raises_error(self):
        task = ParseRSSFeed()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_feed_url_raises_error(self):
        task = ParseRSSFeed()
        with pytest.raises(ValueError):
            task.run(feed_url=None)

    def test_feed_url_init_value_is_used(self, monkeypatch):
        task = ParseRSSFeed(feed_url="test")

        parse = MagicMock()
        monkeypatch.setattr("prefect.tasks.rss.feed.feedparser.parse", parse)

        task.run()
        assert parse.call_args[0][0] == "test"

    def test_feed_url_run_value_is_used(self, monkeypatch):
        task = ParseRSSFeed()

        parse = MagicMock()
        monkeypatch.setattr("prefect.tasks.rss.feed.feedparser.parse", parse)

        task.run(feed_url="test")
        assert parse.call_args[0][0] == "test"

    def test_feed_url_value_is_replaced(self, monkeypatch):
        task = ParseRSSFeed(feed_url="test")

        parse = MagicMock()
        monkeypatch.setattr("prefect.tasks.rss.feed.feedparser.parse", parse)

        task.run(feed_url="b_test")
        assert parse.call_args[0][0] == "b_test"