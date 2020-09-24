import requests
from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs
from typing import Any

import json


class CreateItem(Task):
    """
    Task for creating items in a Monday board

    Args:
        - board_id (int): the id of the board to add the new item
        - group_id (str): the id of the group to add the new item
        - item_name (str): the name of the item to be created
        - column_values (dict, optional): any additional custom columns added to your board
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        board_id: int = None,
        group_id: str = None,
        item_name: str = None,
        column_values: dict = None,
        **kwargs: Any
    ):
        self.board_id = board_id
        self.group_id = group_id
        self.item_name = item_name
        self.column_values = column_values

        super().__init__(**kwargs)

    @defaults_from_attrs("board_id", "group_id", "item_name", "column_values")
    def run(
        self,
        board_id: str = None,
        group_id: str = None,
        item_name: str = None,
        column_values: dict = None,
        monday_api_token: str = "MONDAY_API_TOKEN",
    ) -> None:
        """
        Task run method.

        Args:
            - board_id (int): the id of the board to add the new item
            - group_id (str): the id of the group to add the new item
            - item_name (str): the name of the item to be created
            - column_values (dict, optional): any additional custom columns added to your board
            - monday_api_token (str): the name of the Prefect Secret which stored your Monday
                API Token.

        Returns:
            - int: the id of the item created
        """

        if board_id is None:
            raise ValueError("A board id must be provided.")

        if group_id is None:
            raise ValueError("A group id must be provided")

        if item_name is None:
            raise ValueError("An item name must be provided")

        if monday_api_token is None:
            raise ValueError("An API Token must be provided")

        # prepare mutation
        headers = {"Authorization": monday_api_token}

        variables = {
            "MONDAY_BOARD_ID": board_id,
            "MONDAY_GROUP_ID": group_id,
            "ITEM_NAME": item_name,
        }
        if column_values:
            variables.update({"COLUMN_VALUES": json.dumps(column_values)})

        query = """
            mutation (
                $MONDAY_BOARD_ID:Int!,
                $MONDAY_GROUP_ID:String!,
                $ITEM_NAME:String!,
                $COLUMN_VALUES:JSON) {
                create_item (
                    board_id: $MONDAY_BOARD_ID,
                    group_id: $MONDAY_GROUP_ID,
                    item_name: $ITEM_NAME,
                    column_values: $COLUMN_VALUES)
                {
                    id
                }
            }
        """

        response = requests.post(
            "https://api.monday.com/v2/",
            json={"query": query, "variables": variables},
            headers=headers,
        )
        if response.status_code == 200:
            return response.json()["data"]["create_item"]["id"]
        else:
            raise Exception("Query failed {}. {}".format(response.status_code, query))
