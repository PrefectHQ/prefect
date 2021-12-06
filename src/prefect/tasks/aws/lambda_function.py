import json
from base64 import b64encode

from prefect import Task
from prefect.utilities.aws import get_boto_client
from prefect.utilities.tasks import defaults_from_attrs


class LambdaCreate(Task):
    """
    Task for creating a Lambda function.

    Args:
        - function_name (str): name of the Lambda function to create
        - runtime (str): the identifier of the function's runtime
        - role (str): the Amazon Resource Name of the function's execution role
        - handler (str): the name of the method within your code that Lambda calls
            to execute your function
        - zip_file (str): path to zip file containing code for Lambda function,
            either zip_file or (bucket and bucket_key) must be passed
        - bucket (str): an S3 bucket in the same AWS region as your function
        - bucket_key (str): the Amazon S3 key of the deployment package
        - object_version (str, optional): for versioned S3 objects, the version of the
            deployment package to use
        - description (str, optional): description of Lambda function
        - function_timeout (int, optional): Lambda function timeout in seconds, default is 3 seconds
        - memorysize (int, optional): amount of memory that Lambda function has
            access to in MB, must be a multiple of 64 MB, default is 128
        - publish (bool, optional): set to True to publish the first version of the
            function during creation, defaults to True
        - subnet_ids (List[str], optional): list of subnet ids for vpc
            configuration
        - security_group_ids (List[str], optional): list of security
            group ideas for vpc configuration
        - dead_letter_config (dict, optional): a dead letter queue configuration that
            specifies the queue or topic where Lambda sends asynchronous events
            when they fail processing
        - environment_variables (dict, optional): key-value pairs of environment
            variables to pass to the Lambda function
        - kms_key_arn (str, optional): the ARN of the AWS key management service used
            to encrypt your function's environment variables, if not provided, AWS
            Lambda uses a default service key
        - function_tags (dict, optional): a list of tags to apply to the function, string
            to string map
        - tracing_config (str, optional): set to Active to samle and trace a
            subset of incoming requests with Amazon X-Ray
        - layers (List[str], optional): a list of function layers to add to
            the function's execution environment, specify each layer by its ARN
        - boto_kwargs (dict, optional): additional keyword arguments to forward to the boto client.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        function_name: str,
        runtime: str,
        role: str,
        handler: str,
        zip_file: str = None,
        bucket: str = "",
        bucket_key: str = "",
        object_version: str = None,
        description: str = "",
        function_timeout: int = 3,
        memorysize: int = 128,
        publish: bool = True,
        subnet_ids: list = None,
        security_group_ids: list = None,
        dead_letter_config: dict = None,
        environment_variables: dict = None,
        kms_key_arn: str = "",
        function_tags: dict = None,
        tracing_config: str = "PassThrough",
        layers: list = None,
        boto_kwargs: dict = None,
        **kwargs
    ):
        self.function_name = function_name
        self.runtime = runtime
        self.role = role
        self.handler = handler

        # if zip file is provided, pass this to boto3 create, otherwise pass s3 object
        if zip_file:
            self.code = {"ZipFile": open(zip_file, "rb").read()}
        else:
            self.code = {"S3Bucket": bucket, "S3Key": bucket_key}
            if object_version:
                self.code["S3ObjectVersion"] = object_version

        self.description = description
        self.function_timeout = function_timeout
        self.memorysize = memorysize
        self.publish = publish

        self.vpc_config = {}
        if subnet_ids:
            self.vpc_config["SubnetIds"] = subnet_ids
        if security_group_ids:
            self.vpc_config["SecurityGroupIds"] = security_group_ids

        self.dead_letter_config = dead_letter_config
        self.environment_variables = environment_variables
        self.kms_key_arn = kms_key_arn
        self.function_tags = function_tags
        self.tracing_config = tracing_config
        self.layers = layers

        if boto_kwargs is None:
            self.boto_kwargs = {}
        else:
            self.boto_kwargs = boto_kwargs

        super().__init__(**kwargs)

    def run(self, credentials: dict = None):
        """
        Task run method. Creates Lambda function.

        Args:
            - credentials (dict, optional): your AWS credentials passed from an upstream
                Secret task; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
                passed directly to `boto3`.  If not provided here or in context, `boto3`
                will fall back on standard AWS rules for authentication.

        Returns:
            - json: response from AWS CreateFunction endpoint
        """

        lambda_client = get_boto_client(
            "lambda", credentials=credentials, **self.boto_kwargs
        )

        # create lambda function
        response = lambda_client.create_function(
            FunctionName=self.function_name,
            Runtime=self.runtime,
            Role=self.role,
            Handler=self.handler,
            Code=self.code,
            Description=self.description,
            Timeout=self.function_timeout,
            MemorySize=self.memorysize,
            Publish=self.publish,
            VpcConfig=self.vpc_config,
            DeadLetterConfig=self.dead_letter_config or {},
            Environment={"Variables": self.environment_variables or {}},
            KMSKeyArn=self.kms_key_arn,
            TracingConfig={"Mode": self.tracing_config},
            Tags=self.function_tags or {},
            Layers=self.layers or [],
        )

        return response


class LambdaDelete(Task):
    """
    Task for deleting a Lambda function.

    Args:
        - function_name (str): name of the Lambda function to delete
        - qualifier (str, optional): specify a version to delete, if not
            provided, the function will be deleted entirely
        - boto_kwargs (dict, optional): additional keyword arguments to forward to the boto client.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        function_name: str,
        qualifier: str = "",
        boto_kwargs: dict = None,
        **kwargs
    ):
        self.function_name = function_name
        self.qualifier = qualifier

        if boto_kwargs is None:
            self.boto_kwargs = {}
        else:
            self.boto_kwargs = boto_kwargs

        super().__init__(**kwargs)

    def run(self, credentials: dict = None):
        """
        Task run method. Deletes Lambda function.

        Args:
            - credentials (dict, optional): your AWS credentials passed from an upstream
                Secret task; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
                passed directly to `boto3`.  If not provided here or in context, `boto3`
                will fall back on standard AWS rules for authentication.

        Returns:
            - dict: response from AWS DeleteFunction endpoint
        """

        lambda_client = get_boto_client(
            "lambda", credentials=credentials, **self.boto_kwargs
        )

        # delete function, depending on if qualifier provided
        if len(self.qualifier) > 0:
            response = lambda_client.delete_function(
                FunctionName=self.function_name, Qualifier=self.qualifier
            )
            return response

        response = lambda_client.delete_function(FunctionName=self.function_name)
        return response


class LambdaInvoke(Task):
    """
    Task to invoke a Lambda function.

    Args:
        - function_name (str): the name of the Lambda funciton to invoke
        - invocation_type (str, optional): the invocation type of Lambda
            function, default is RequestResponse other options include
            Event and DryRun
        - log_type (str, optional): set to 'Tail' to include the execution
            log in the response
        - client_context (dict, optional): data to pass to the function in the
            context object, dict object will be transformed into base64 encoded
            json automatically
        - payload (bytes or seekable file-like object): the JSON provided to
            Lambda function as input
        - qualifier (str, optional): specify a version or alias to invoke a
            published version of the function, defaults to $LATEST
        - boto_kwargs (dict, optional): additional keyword arguments to forward to the boto client.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        function_name: str,
        invocation_type: str = "RequestResponse",
        log_type: str = "None",
        client_context: dict = None,
        payload: str = json.dumps(None),
        qualifier: str = "$LATEST",
        boto_kwargs: dict = None,
        **kwargs
    ):
        self.function_name = function_name
        self.invocation_type = invocation_type
        self.log_type = log_type

        # encode input dictionary as base64 json
        self.client_context = self._encode_lambda_context(**(client_context or {}))

        self.payload = payload
        self.qualifier = qualifier

        if boto_kwargs is None:
            self.boto_kwargs = {}
        else:
            self.boto_kwargs = boto_kwargs

        super().__init__(**kwargs)

    def _encode_lambda_context(self, custom=None, env=None, client=None):

        """
        Utility function for encoding Lambda context

        Args:
            - custom (dict, optional): key-value  pairs to pass to custom context
            - env (dict, optional): key-value pairs to pass to environment context
            - client (dict, optional): key-value pairs to pass to client context

        Returns:
            - json: base64 encoded json object
        """

        client_context = dict(custom=custom, env=env, client=client)
        json_context = json.dumps(client_context).encode("utf-8")
        return b64encode(json_context).decode("utf-8")

    @defaults_from_attrs("function_name", "payload")
    def run(
        self,
        function_name: str = None,
        payload: str = None,
        credentials: dict = None,
    ):
        """
        Task run method. Invokes Lambda function.

        Args:
            - function_name (str): the name of the Lambda funciton to invoke
            - payload (bytes or seekable file-like object): the JSON provided to
                Lambda function as input
            - credentials (dict, optional): your AWS credentials passed from an upstream
                Secret task; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
                passed directly to `boto3`.  If not provided here or in context, `boto3`
                will fall back on standard AWS rules for authentication.

        Returns:
            - dict : response from AWS Invoke endpoint
        """

        lambda_client = get_boto_client(
            "lambda", credentials=credentials, **self.boto_kwargs
        )

        # invoke lambda function
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType=self.invocation_type,
            LogType=self.log_type,
            ClientContext=self.client_context,
            Payload=payload,
            Qualifier=self.qualifier,
        )

        return response


class LambdaList(Task):
    """
    Task to list Lambda functions.

    Args:
        - master_region (str, optional): for Lambda@Edge functions, the AWS
            region of the master function
        - function_version (str, optional): the version of a function,
            default is 'ALL'
        - marker (str, optional): specify the pagination token that's returned
            by a previous request to retreive the next page of results
        - max_items (int, optional): specify a value between 1 and 50 to limit
            the number of functions in the response
        - boto_kwargs (dict, optional): additional keyword arguments to forward to the boto client.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        master_region: str = "ALL",
        function_version: str = "ALL",
        marker: str = None,
        max_items: int = 50,
        boto_kwargs: dict = None,
        **kwargs
    ):
        self.master_region = master_region
        self.function_version = function_version
        self.marker = marker
        self.max_items = max_items

        if boto_kwargs is None:
            self.boto_kwargs = {}
        else:
            self.boto_kwargs = boto_kwargs

        super().__init__(**kwargs)

    def run(self, credentials: dict = None):
        """
        Task fun method. Lists all Lambda functions.

        Args:
            - credentials (dict, optional): your AWS credentials passed from an upstream
                Secret task; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
                passed directly to `boto3`.  If not provided here or in context, `boto3`
                will fall back on standard AWS rules for authentication.

        Returns:
            - dict : a list of Lambda functions from AWS ListFunctions endpoint
        """

        lambda_client = get_boto_client(
            "lambda", credentials=credentials, **self.boto_kwargs
        )

        # list functions, optionally passing in marker if not None
        if self.marker:
            response = lambda_client.list_functions(
                MasterRegion=self.master_region,
                FunctionVersion=self.function_version,
                Marker=self.marker,
                MaxItems=self.max_items,
            )
            return response

        response = lambda_client.list_functions(
            MasterRegion=self.master_region,
            FunctionVersion=self.function_version,
            MaxItems=self.max_items,
        )

        return response
