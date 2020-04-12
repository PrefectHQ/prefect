from unittest.mock import MagicMock

import pytest

import prefect
from prefect.tasks.twitter import LoadTweetReplies
from prefect.utilities.configuration import set_temporary_config


class TestLoadTweetReplies:
    def test_initialize_with_nothing_sets_defaults(self):
        task = LoadTweetReplies()
        assert task.user is None
        assert task.tweet_id is None

    def test_initialize_kwargs_are_processed(self):
        task = LoadTweetReplies(checkpoint=True, name="test")
        assert task.name == "test"
        assert task.checkpoint is True

    @pytest.mark.parametrize("attr", ["user", "tweet_id"])
    def test_initializes_attr_from_kwargs(self, attr):
        task = LoadTweetReplies(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"
