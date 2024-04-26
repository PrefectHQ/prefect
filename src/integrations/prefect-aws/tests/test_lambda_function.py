import inspect
import io
import json
import zipfile
from typing import Optional

import boto3
import pytest
from botocore.response import StreamingBody
from moto import mock_iam, mock_lambda
from prefect_aws.credentials import AwsCredentials
from prefect_aws.lambda_function import LambdaFunction


@pytest.fixture
def lambda_mock(aws_credentials: AwsCredentials):
    with mock_lambda():
        yield boto3.client(
            "lambda",
            region_name=aws_credentials.region_name,
        )


@pytest.fixture
def iam_mock(aws_credentials: AwsCredentials):
    with mock_iam():
        yield boto3.client(
            "iam",
            region_name=aws_credentials.region_name,
        )


@pytest.fixture
def mock_iam_rule(iam_mock):
    yield iam_mock.create_role(
        RoleName="test-role",
        AssumeRolePolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }
        ),
    )


def handler_a(event, context):
    if isinstance(event, dict):
        if "error" in event:
            raise Exception(event["error"])
        event["foo"] = "bar"
    else:
        event = {"foo": "bar"}
    return event


LAMBDA_TEST_CODE = inspect.getsource(handler_a)


@pytest.fixture
def mock_lambda_code():
    with io.BytesIO() as f:
        with zipfile.ZipFile(f, mode="w") as z:
            z.writestr("foo.py", LAMBDA_TEST_CODE)
        f.seek(0)
        yield f.read()


@pytest.fixture
def mock_lambda_function(lambda_mock, mock_iam_rule, mock_lambda_code):
    r = lambda_mock.create_function(
        FunctionName="test-function",
        Runtime="python3.10",
        Role=mock_iam_rule["Role"]["Arn"],
        Handler="foo.handler",
        Code={"ZipFile": mock_lambda_code},
    )
    r2 = lambda_mock.publish_version(
        FunctionName="test-function",
    )
    r["Version"] = r2["Version"]
    yield r


def handler_b(event, context):
    event = {"data": [1, 2, 3]}
    return event


LAMBDA_TEST_CODE_V2 = inspect.getsource(handler_b)


@pytest.fixture
def mock_lambda_code_v2():
    with io.BytesIO() as f:
        with zipfile.ZipFile(f, mode="w") as z:
            z.writestr("foo.py", LAMBDA_TEST_CODE_V2)
        f.seek(0)
        yield f.read()


@pytest.fixture
def add_lambda_version(mock_lambda_function, lambda_mock, mock_lambda_code_v2):
    r = mock_lambda_function.copy()
    lambda_mock.update_function_code(
        FunctionName="test-function",
        ZipFile=mock_lambda_code_v2,
    )
    r2 = lambda_mock.publish_version(
        FunctionName="test-function",
    )
    r["Version"] = r2["Version"]
    yield r


@pytest.fixture
def lambda_function(aws_credentials):
    return LambdaFunction(
        function_name="test-function",
        aws_credentials=aws_credentials,
    )


def make_patched_invocation(client, handler):
    """Creates a patched invoke method for moto lambda. The method replaces
    the response 'Payload' with the result of the handler function.
    """
    true_invoke = client.invoke

    def invoke(*args, **kwargs):
        """Calls the true invoke and replaces the Payload with its result."""
        result = true_invoke(*args, **kwargs)
        blob = json.dumps(
            handler(
                event=kwargs.get("Payload"),
                context=kwargs.get("ClientContext"),
            )
        ).encode()
        result["Payload"] = StreamingBody(io.BytesIO(blob), len(blob))
        return result

    return invoke


@pytest.fixture
def mock_invoke(
    lambda_function: LambdaFunction, handler, monkeypatch: pytest.MonkeyPatch
):
    """Fixture to patch the invocation response's 'Payload' field.

    When `result["Payload"].read` is called, moto attempts to run the function
    in a Docker container and return the result. This is total overkill, so
    we actually call the handler with the given arguments.
    """
    client = lambda_function._get_lambda_client()

    monkeypatch.setattr(
        client,
        "invoke",
        make_patched_invocation(client, handler),
    )

    def _get_lambda_client():
        return client

    monkeypatch.setattr(
        lambda_function,
        "_get_lambda_client",
        _get_lambda_client,
    )

    yield


class TestLambdaFunction:
    def test_init(self, aws_credentials):
        function = LambdaFunction(
            function_name="test-function",
            aws_credentials=aws_credentials,
        )
        assert function.function_name == "test-function"
        assert function.qualifier is None

    @pytest.mark.parametrize(
        "payload,expected,handler",
        [
            ({"foo": "baz"}, {"foo": "bar"}, handler_a),
            (None, {"foo": "bar"}, handler_a),
        ],
    )
    def test_invoke_lambda_payloads(
        self,
        payload: Optional[dict],
        expected: dict,
        handler,
        mock_lambda_function,
        lambda_function: LambdaFunction,
        mock_invoke,
    ):
        result = lambda_function.invoke(payload)
        assert result["StatusCode"] == 200
        response_payload = json.loads(result["Payload"].read())
        assert response_payload == expected

    @pytest.mark.parametrize("handler", [handler_a])
    def test_invoke_lambda_tail(
        self, lambda_function: LambdaFunction, mock_lambda_function, mock_invoke
    ):
        result = lambda_function.invoke(tail=True)
        assert result["StatusCode"] == 200
        response_payload = json.loads(result["Payload"].read())
        assert response_payload == {"foo": "bar"}
        assert "LogResult" in result

    @pytest.mark.parametrize("handler", [handler_a])
    def test_invoke_lambda_client_context(
        self, lambda_function: LambdaFunction, mock_lambda_function, mock_invoke
    ):
        # Just making sure boto doesn't throw an error
        result = lambda_function.invoke(client_context={"bar": "foo"})
        assert result["StatusCode"] == 200
        response_payload = json.loads(result["Payload"].read())
        assert response_payload == {"foo": "bar"}

    @pytest.mark.parametrize(
        "func_fixture,expected,handler",
        [
            ("mock_lambda_function", {"foo": "bar"}, handler_a),
            ("add_lambda_version", {"data": [1, 2, 3]}, handler_b),
        ],
    )
    def test_invoke_lambda_qualifier(
        self,
        func_fixture,
        expected,
        lambda_function: LambdaFunction,
        mock_invoke,
        request,
    ):
        func_fixture = request.getfixturevalue(func_fixture)
        try:
            lambda_function.qualifier = func_fixture["Version"]
            result = lambda_function.invoke()
            assert result["StatusCode"] == 200
            response_payload = json.loads(result["Payload"].read())
            assert response_payload == expected
        finally:
            lambda_function.qualifier = None
