"""
This example is [based on work by Matt Dickenson](https://mattdickenson.com/2019/03/02/extract-replies-to-tweet/)
and shows how to use Prefect to build a flow that loads replies to a tweet, then inserts those
replies into Airtable.

This flow relies heavily on local secrets to authenticate with both Twitter and Airtable.
"""

import prefect
from prefect import Flow, Parameter, task, unmapped
from prefect.tasks.airtable import WriteAirtableRow
from prefect.tasks.twitter import LoadTweetReplies

# ------------------------------------------------------------
# Secrets
#
# Fill out your credentials here for the local runs
# ------------------------------------------------------------

TWITTER_CREDS = {
    "api_key": "🤫",
    "api_secret": "🤫",
    "access_token": "🤫",
    "access_token_secret": "🤫",
}

AIRTABLE_API_KEY = "🤫"

# ------------------------------------------------------------
# Build the flow
#
# For this flow, we:
#   - create parameters
#   - create a small task to reformat tweets
#   - wire up the flow with our parameters, reformatter, and two task library tasks
# ------------------------------------------------------------

twitter_user = Parameter("twitter_user")
tweet_id = Parameter("tweet_id")
airtable_base = Parameter("airtable_base")
airtable_table = Parameter("airtable_table")


@task
def format_tweet(tweet) -> dict:
    """
    This task takes a tweet object and returns a dictionary containing its `user` and `text`
    """
    return dict(user=tweet.user.screen_name, text=tweet.text)


with Flow("Tweets to Airtable") as flow:

    # load tweets
    replies = LoadTweetReplies()(user=twitter_user, tweet_id=tweet_id)

    # map over each tweet to format it for Airtable
    formatted_replies = format_tweet.map(replies)

    # map over each formatted tweet and insert it to Airtable
    WriteAirtableRow().map(
        formatted_replies,
        base_key=unmapped(airtable_base),
        table_name=unmapped(airtable_table),
    )


# ------------------------------------------------------------
# Run the flow
#
# Because we're running this flow locally, we create a secrets context to provide
# our credentials, then call flow.run() with our parameter values
# ------------------------------------------------------------
# set up the local secrets
with prefect.context(
    secrets=dict(
        TWITTER_API_CREDENTIALS=TWITTER_CREDS, AIRTABLE_API_KEY=AIRTABLE_API_KEY
    )
):

    # run the flow
    state = flow.run(
        twitter_user="PrefectIO",
        tweet_id="1046873748559814656",
        airtable_base="<AN AIRTABLE BASE>",
        airtable_table="<AN AIRTABLE TABLE>",
    )
