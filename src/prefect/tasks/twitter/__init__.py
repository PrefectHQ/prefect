"""
Tasks for interacting with Twitter.
"""
try:
    from prefect.tasks.twitter.twitter import LoadTweetReplies
except ImportError as exc:
    raise ImportError(
        'Using `prefect.tasks.twitter` requires Prefect to be installed with the "twitter" extra.'
    ) from exc

__all__ = ["LoadTweetReplies"]
