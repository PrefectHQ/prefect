from typing import Any

import tweepy

from prefect.core import Task
from prefect.utilities.tasks import defaults_from_attrs


class LoadTweetReplies(Task):
    """
    A task for loading replies to a specific user's tweet. This task works by querying the
    100 most recent replies to that user, then filtering for those that match the specified
    tweet id.

    This code is based on the work of Matt Dickenson @mcdickenson
    https://mattdickenson.com/2019/03/02/extract-replies-to-tweet/

    Note that _all_ initialization settings can be provided / overwritten at runtime.

    Args:
        - user (str): a Twitter user
        - tweet_id (str): a tweet ID; replies to this tweet will be retrieved
        - **kwargs (optional): additional kwargs to pass to the `Task` constructor
    """

    def __init__(self, user: str = None, tweet_id: str = None, **kwargs: Any):
        self.user = user
        self.tweet_id = tweet_id
        super().__init__(**kwargs)

    @defaults_from_attrs("user", "tweet_id")
    def run(
        self, user: str = None, tweet_id: str = None, credentials: dict = None
    ) -> list:
        """
        Args:
            - user (str): a Twitter user
            - tweet_id (str): a tweet ID; replies to this tweet will be retrieved
            - credentials(dict): a JSON document with four keys:
                "api_key", "api_secret", "access_token", and "access_token_secret".
        """
        if credentials is None:
            raise ValueError("Credentials dictionary wasn't provided.")

        auth = tweepy.OAuthHandler(credentials["api_key"], credentials["api_secret"])
        auth.set_access_token(
            credentials["access_token"], credentials["access_token_secret"]
        )

        api = tweepy.API(auth)

        cursor = tweepy.Cursor(
            api.search, q="to:" + user, result_type="recent", timeout=999999
        )

        replies = []
        for tweet in cursor.items(100):
            if hasattr(tweet, "in_reply_to_status_id_str"):
                if tweet.in_reply_to_status_id_str == tweet_id:
                    replies.append(tweet)

        return replies
