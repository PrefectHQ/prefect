import boto3

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class StepActivate(Task):
    """
    Task for activating an AWS Step Function.

    Args:
        - state_machine_arn (str): the Amazon Resource Name (ARN) of the state machine
            to execute
        - execution_name (str): the name of the execution, this name must be unique for
            your AWS account, region, and state machine for 90 days
        - execution_input (str, optional): string that contains the JSON input data for
            the execution
        - aws_credentials_secret (str, optional): the name of the Prefect Secret
            that stores your AWS credentials; this Secret must be a JSON string
            with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY`
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        state_machine_arn: str,
        execution_name: str,
        execution_input: str = "{}",
        aws_credentials_secret: str = "AWS_CREDENTIALS",
        **kwargs
    ):
        self.state_machine_arn = state_machine_arn
        self.execution_name = execution_name
        self.execution_input = execution_input
        self.aws_credentials_secret = aws_credentials_secret
        super().__init__(**kwargs)

    @defaults_from_attrs("aws_credentials_secret")
    def run(self, aws_credentials_secret: str = "AWS_CREDENTIALS"):
        """
        Task run method. Activates AWS Step function.

        Args:
            - aws_credentials_secret (str, optional): the name of the Prefect Secret
                that stores your AWS credentials; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY`

        Returns:
            - dict: response from AWS StartExecution endpoint
        """

        ## get AWS credentials
        aws_credentials = Secret(aws_credentials_secret).get()
        aws_access_key = aws_credentials["ACCESS_KEY"]
        aws_secret_access_key = aws_credentials["SECRET_ACCESS_KEY"]
        step_client = boto3.client(
            "stepfunctions",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_access_key,
        )

        response = step_client.start_execution(
            stateMachineArn=self.state_machine_arn,
            name=self.execution_name,
            input=self.execution_input,
        )

        return response
