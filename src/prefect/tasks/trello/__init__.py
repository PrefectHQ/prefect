"""
Tasks for interacting with Trello
Note, to authenticate with the Trello API use upstream PrefectSecret tasks to pass in
'"TRELLO_API_KEY"' (see https://trello.com/app-key while logged in)
and '"TRELLO_SERVER_TOKEN"' (click the 'Token' link on https://trello.com/app-key to generate)
"""

from prefect.tasks.trello.trello import CreateCard

__all__ = ["CreateCard"]
