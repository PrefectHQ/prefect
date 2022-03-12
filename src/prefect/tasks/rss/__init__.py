"""
Tasks for interacting with RSS feeds.
"""
try:
    from prefect.tasks.rss.feed import ParseRSSFeed
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.rss` requires Prefect to be installed with the "rss" extra.'
    ) from err

__all__ = ["ParseRSSFeed"]
