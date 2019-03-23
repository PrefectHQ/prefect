"""
Tasks for interacting with Twitter.

The default Twitter credential secret name is `"TWITTER_API_CREDENTIALS"`, and should be a JSON document with four keys: `"api_key"`, `"api_secret"`, `"access_token"`, and `"access_token_secret"`
"""
try:
    from prefect.tasks.twitter.twitter import LoadTweetReplies
except ImportError:
    raise ImportError(
        'Using `prefect.tasks.twitter` requires Prefect to be installed with the "twitter" extra.'
    )
