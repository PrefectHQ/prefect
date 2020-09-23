import requests
from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs
from typing import Any


class CreateItem(Task):
    """
    Task for creating items in Monday

    Args:
        - monday_personal_token
        - board_id
        - group_id
        - item_name
        - column_values
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
            - TODO: data to create item with
            - monday_api_token

        Returns:
            - int: the id of the item created
        """

        if board_id is None:
            raise ValueError("A board id must be provided.")

        if group_id is None:
            raise ValueError("A group id must be provided")

        if item_name is None:
            raise ValueError("An item name must be provided")

        # prepare mutation
        headers = {
            "Authorization": monday_api_token
        }

        variables = {"MONDAY_BOARD_ID": board_id, "MONDAY_GROUP_ID": group_id, "ITEM_NAME": item_name}

        query = """
            mutation ($MONDAY_BOARD_ID:Int!, $MONDAY_GROUP_ID:String!, $ITEM_NAME:String!) {
                create_item (board_id: $MONDAY_BOARD_ID, group_id: $MONDAY_GROUP_ID, item_name: $ITEM_NAME)
                {
                    id
                }
            }
        """

        response = requests.post('https://api.monday.com/v2/', json={'query': query, 'variables': variables},
                                 headers=headers)
        if response.status_code == 200:
            return response.json()["data"]["create_item"]["id"]
        else:
            raise Exception("Query failed {}. {}".format(response.status_code, query))
