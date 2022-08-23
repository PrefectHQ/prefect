from prefect.tasks.databricks import DatabricksGetJobID, DatabricksRunNow
from prefect.tasks.databricks.databricks_hook import DatabricksHook


class DatabricksHookTestOverride(DatabricksHook):
    """
    Overrides `DatabricksHook` to avoid making actual API calls
    and return mocked responses instead

    Args:
        - mocked_response (dict): JSON response of API call
    """

    def __init__(self, mocked_response={}, **kwargs) -> None:
        self.mocked_response = mocked_response
        super().__init__(self, **kwargs)

    def _do_api_call(self, endpoint_info, json):
        return self.mocked_response


class DatabricksRunNowTestOverride(DatabricksRunNow):
    """
    Overrides `DatabricksRunNow` to allow mocked API responses
    to be returned using `DatabricksHookTestOverride`

    Args:
        - mocked_response (dict): JSON response of API call
    """

    def __init__(self, mocked_response, **kwargs) -> None:
        self.mocked_response = mocked_response
        super().__init__(**kwargs)

    def _get_hook(self, *_):
        return DatabricksHookTestOverride(self.mocked_response)


class DatabricksGetJobIDTestOverride(DatabricksGetJobID):
    """
    Overrides `DatabricksGetJobID` to allow mocked API responses
    to be returned using `DatabricksHookTestOverride`.

    Args:
        - mocked_response (dict): JSON response of API call.
    """

    def __init__(self, mocked_response, **kwargs) -> None:
        self.mocked_response = mocked_response
        super().__init__(**kwargs)

    def _get_hook(self):
        return DatabricksHookTestOverride(self.mocked_response)
