from prefect import Task
import requests
from prefect.utilities.tasks import defaults_from_attrs
from typing import Any


class CreateCard(Task):
    """
    Task for creating a card on Trello, given the list to add it to.

    Args:
      - list_id (str): the id of the list to add the new item.
      - card_name (str, optional): the title of the card to add
      - card_info (str, optional): the description for the back of the card
      - **kwargs (dict, optional): additional arguments to pass to the Task constructor
    """

    def __init__(
        self,
        list_id: str = None,
        card_name: str = None,
        card_info: str = None,
        **kwargs: Any
    ):
        self.list_id = list_id
        self.card_name = card_name
        self.card_info = card_info

        super().__init__(**kwargs)

    @defaults_from_attrs("list_id", "card_name", "card_info")
    def run(
        self,
        list_id: str = None,
        card_name: str = None,
        card_info: str = None,
        trello_api_key: str = "TRELLO_API_KEY",
        trello_server_token: str = "TRELLO_SERVER_TOKEN",
    ) -> None:
        """
        Task run method.

        Args:
          - list_id (str): the id of the list to add the new item.
          - card_name (str, optional): the title of the card to add
          - card_info (str, optional): the description for the back of the card
          - trello_api_key (str): the name of the Prefect Secret where you've stored your API key
          - trello_server_token (str): the name of the Prefect Secret
          where you've stored your server token

        Returns:
          - Status code of POST request (200 for success)
        """

        if list_id is None:
            raise ValueError(
                """A list ID must be provided. See
https://developer.atlassian.com/cloud/trello/rest/api-group-boards/#api-boards-id-lists-get
for details."""
            )

        if trello_api_key is None:
            raise ValueError(
                "An API key must be provided. See https://trello.com/app-key while logged in."
            )

        if trello_server_token is None:
            raise ValueError(
                """A server token must be provided.
Click the 'Token' link on https://trello.com/app-key to generate."""
            )

        url = "https://api.trello.com/1/cards/"
        params = {
            "key": trello_api_key,
            "token": trello_server_token,
            "idList": list_id,
            "name": card_name,
            "desc": card_info,
        }
        response = requests.post(url, data=params)

        return response
