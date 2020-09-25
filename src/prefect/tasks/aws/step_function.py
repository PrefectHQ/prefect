from prefect import Task
from prefect.utilities.aws import get_boto_client


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
        - boto_kwargs (dict, optional): additional keyword arguments to forward to the boto client.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        state_machine_arn: str,
        execution_name: str,
        execution_input: str = "{}",
        boto_kwargs: dict = None,
        **kwargs
    ):
        self.state_machine_arn = state_machine_arn
        self.execution_name = execution_name
        self.execution_input = execution_input

        if boto_kwargs is None:
            self.boto_kwargs = {}
        else:
            self.boto_kwargs = boto_kwargs

        super().__init__(**kwargs)

    def run(self, credentials: dict = None):
        """
        Task run method. Activates AWS Step function.

        Args:
            - credentials (dict, optional): your AWS credentials passed from an upstream
                Secret task; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
                passed directly to `boto3`.  If not provided here or in context, `boto3`
                will fall back on standard AWS rules for authentication.

        Returns:
            - dict: response from AWS StartExecution endpoint
        """

        step_client = get_boto_client(
            "stepfunctions", credentials=credentials, **self.boto_kwargs
        )

        response = step_client.start_execution(
            stateMachineArn=self.state_machine_arn,
            name=self.execution_name,
            input=self.execution_input,
        )

        return response
