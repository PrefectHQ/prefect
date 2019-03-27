from typing import Any

import feedparser

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class ParseRSSFeed(Task):
    """
    Task for parsing RSS feeds.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - feed_url (str): A remote URL pointing to an RSS feed
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(self, feed_url: str = None, **kwargs: Any):
        self.feed_url = feed_url

        super().__init__(**kwargs)

    @defaults_from_attrs("feed_url")
    def run(self, feed_url: str = None) -> "feedparser.FeedParserDict":
        """
        Task run method.

        Args:
            - feed_url (str): A remote URL pointing to an RSS feed

        Return:
            - FeedParserDict: A dictionary representing the information from the
                parsed feed. The object is accessable through indexing and attributes.

        Raises:
            - ValueError: if `feed_url` is `None`
        """
        if not feed_url:
            raise ValueError("The feed_url must be provided.")

        return feedparser.parse(feed_url)
