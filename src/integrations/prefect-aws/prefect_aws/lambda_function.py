"""Integrations with AWS Lambda.

Examples:

    Run a lambda function with a payload

    ```python
    LambdaFunction(
        function_name="test-function",
        aws_credentials=aws_credentials,
    ).invoke(payload={"foo": "bar"})
    ```

    Specify a version of a lambda function

    ```python
    LambdaFunction(
        function_name="test-function",
        qualifier="1",
        aws_credentials=aws_credentials,
    ).invoke()
    ```

    Invoke a lambda function asynchronously

    ```python
    LambdaFunction(
        function_name="test-function",
        aws_credentials=aws_credentials,
    ).invoke(invocation_type="Event")
    ```

    Invoke a lambda function and return the last 4 KB of logs

    ```python
    LambdaFunction(
        function_name="test-function",
        aws_credentials=aws_credentials,
    ).invoke(tail=True)
    ```

    Invoke a lambda function with a client context

    ```python
    LambdaFunction(
        function_name="test-function",
        aws_credentials=aws_credentials,
    ).invoke(client_context={"bar": "foo"})
    ```

"""
import json
from typing import Literal, Optional

from pydantic import VERSION as PYDANTIC_VERSION

from prefect.blocks.core import Block
from prefect.utilities.asyncutils import run_sync_in_worker_thread, sync_compatible

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field
else:
    from pydantic import Field

from prefect_aws.credentials import AwsCredentials


class LambdaFunction(Block):
    """Invoke a Lambda function. This block is part of the prefect-aws
    collection. Install prefect-aws with `pip install prefect-aws` to use this
    block.

    Attributes:
        function_name: The name, ARN, or partial ARN of the Lambda function to
            run. This must be the name of a function that is already deployed
            to AWS Lambda.
        qualifier: The version or alias of the Lambda function to use when
            invoked. If not specified, the latest (unqualified) version of the
            Lambda function will be used.
        aws_credentials: The AWS credentials to use to connect to AWS Lambda
            with a default factory of AwsCredentials.

    """

    _block_type_name = "Lambda Function"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/d74b16fe84ce626345adf235a47008fea2869a60-225x225.png"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-aws/s3/#prefect_aws.lambda_function.LambdaFunction"  # noqa

    function_name: str = Field(
        title="Function Name",
        description=(
            "The name, ARN, or partial ARN of the Lambda function to run. This"
            " must be the name of a function that is already deployed to AWS"
            " Lambda."
        ),
    )
    qualifier: Optional[str] = Field(
        default=None,
        title="Qualifier",
        description=(
            "The version or alias of the Lambda function to use when invoked. "
            "If not specified, the latest (unqualified) version of the Lambda "
            "function will be used."
        ),
    )
    aws_credentials: AwsCredentials = Field(
        title="AWS Credentials",
        default_factory=AwsCredentials,
        description="The AWS credentials to invoke the Lambda with.",
    )

    class Config:
        """Lambda's pydantic configuration."""

        smart_union = True

    def _get_lambda_client(self):
        """
        Retrieve a boto3 session and Lambda client
        """
        boto_session = self.aws_credentials.get_boto3_session()
        lambda_client = boto_session.client("lambda")
        return lambda_client

    @sync_compatible
    async def invoke(
        self,
        payload: dict = None,
        invocation_type: Literal[
            "RequestResponse", "Event", "DryRun"
        ] = "RequestResponse",
        tail: bool = False,
        client_context: Optional[dict] = None,
    ) -> dict:
        """
        [Invoke](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lambda/client/invoke.html)
        the Lambda function with the given payload.

        Args:
            payload: The payload to send to the Lambda function.
            invocation_type: The invocation type of the Lambda function. This
                can be one of "RequestResponse", "Event", or "DryRun". Uses
                "RequestResponse" by default.
            tail: If True, the response will include the base64-encoded last 4
                KB of log data produced by the Lambda function.
            client_context: The client context to send to the Lambda function.
                Limited to 3583 bytes.

        Returns:
            The response from the Lambda function.

        Examples:

            ```python
            from prefect_aws.lambda_function import LambdaFunction
            from prefect_aws.credentials import AwsCredentials

            credentials = AwsCredentials()
            lambda_function = LambdaFunction(
                function_name="test_lambda_function",
                aws_credentials=credentials,
            )
            response = lambda_function.invoke(
                payload={"foo": "bar"},
                invocation_type="RequestResponse",
            )
            response["Payload"].read()
            ```
            ```txt
            b'{"foo": "bar"}'
            ```

        """
        # Add invocation arguments
        kwargs = dict(FunctionName=self.function_name)

        if payload:
            kwargs["Payload"] = json.dumps(payload).encode()

        # Let boto handle invalid invocation types
        kwargs["InvocationType"] = invocation_type

        if self.qualifier is not None:
            kwargs["Qualifier"] = self.qualifier

        if tail:
            kwargs["LogType"] = "Tail"

        if client_context is not None:
            # For some reason this is string, but payload is bytes
            kwargs["ClientContext"] = json.dumps(client_context)

        # Get client and invoke
        lambda_client = await run_sync_in_worker_thread(self._get_lambda_client)
        return await run_sync_in_worker_thread(lambda_client.invoke, **kwargs)
