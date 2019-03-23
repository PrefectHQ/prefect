import pytest
from unittest.mock import MagicMock

import prefect
from prefect.tasks.twitter import LoadTweetReplies
from prefect.utilities.configuration import set_temporary_config


class TestLoadTweetReplies:
    def test_initialize_with_nothing_sets_defaults(self):
        task = LoadTweetReplies()
        assert task.user is None
        assert task.tweet_id is None
        assert task.credentials_secret is "twitter_api_credentials"

    def test_initialize_kwargs_are_processed(self):
        task = LoadTweetReplies(checkpoint=True, name="test")
        assert task.name == "test"
        assert task.checkpoint is True

    @pytest.mark.parametrize("attr", ["user", "tweet_id", "credentials_secret"])
    def test_initializes_attr_from_kwargs(self, attr):
        task = LoadTweetReplies(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"

    def test_creds_are_pulled_from_secret_at_runtime(self, monkeypatch):
        task = LoadTweetReplies()

        tweepy = MagicMock()
        monkeypatch.setattr("prefect.tasks.twitter.twitter.tweepy", tweepy)

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    twitter_api_credentials={
                        "api_key": "a",
                        "api_secret": "b",
                        "access_token": "c",
                        "access_token_secret": "d",
                    }
                )
            ):
                task.run(user="")

        assert tweepy.OAuthHandler.call_args[0] == ("a", "b")
