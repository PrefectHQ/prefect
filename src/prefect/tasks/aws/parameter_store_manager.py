from prefect.tasks.secrets.base import SecretBase
from prefect.utilities.aws import get_boto_client
from prefect.utilities.tasks import defaults_from_attrs


class AWSParametersManager(SecretBase):
    """
    Task for retrieving values from AWS SSM Parameters Store and returning the parameter value.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.
    For authentication, there are two options: you can set the `AWS_CREDENTIALS` Prefect Secret
    containing your AWS access keys, which will be passed directly to the `boto3` client, or you
    can [configure your flow's runtime
    environment](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#guide-configuration)
    for `boto3`.

    Args:
        - parameter_name (str, optional): The name of the parameter to retrieve via SSM.
        - boto_kwargs (dict, optional): Additional keyword arguments to forward to the boto client.
        - **kwargs (dict, optional): Additional keyword arguments to pass to the
            Task constructor.
    """

    def __init__(self, parameter_name: str = None, boto_kwargs: dict = None, **kwargs):
        self.parameter_name = parameter_name

        if boto_kwargs is None:
            self.boto_kwargs = {}
        else:
            self.boto_kwargs = boto_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs("parameter_name", "boto_kwargs")
    def run(
        self,
        parameter_name: str = None,
        credentials: str = None,
        boto_kwargs: dict = None,
    ) -> str:
        """
        Task run method.

        Args:
            - parameter_name (str): The name of the parameter to retrieve from SSM.
            - credentials (dict, optional): Your AWS credentials passed from an upstream
                Secret task; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
                passed directly to `boto3`. If not provided here or in context, `boto3`
                will fall back on standard AWS rules for authentication.
            - boto_kwargs (dict, optional): Additional keyword arguments to forward to the boto client.

        Returns:
            - str: The parameter value, as a string.
        """

        if parameter_name is None:
            raise ValueError("A parameter name must be provided.")

        ssm_client = get_boto_client("ssm", credentials=credentials, **boto_kwargs)

        parameter_response = ssm_client.get_parameter(Name=parameter_name)

        parameter_value = str(parameter_response["Parameter"]["Value"])

        return parameter_value
