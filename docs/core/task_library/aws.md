---
title: AWS
---

# Amazon Web Services

A collection of tasks for interacting with AWS resources.

Note that all tasks require a Prefect Secret called `"AWS_CREDENTIALS"` that should be a JSON
document with two keys: `"ACCESS_KEY"` and `"SECRET_ACCESS_KEY"`.

## LambdaCreate <Badge text="task"/>

Task for creating a Lambda function.

[API Reference](/api/unreleased/tasks/aws.html#lambdacreate)

## LambdaDelete <Badge text="task"/>

Task for deleting a Lambda function.

[API Reference](/api/unreleased/tasks/aws.html#lambdadelete)

## LambdaInvoke <Badge text="task"/>

Task for invoking a Lambda function.

[API Reference](/api/unreleased/tasks/aws.html#lambdainvoke)

## LambdaList <Badge text="task"/>

Task for listing Lambda functions.

[API Reference](/api/unreleased/tasks/aws.html#lambdalist)

## S3Download <Badge text="task"/>

Task for downloading data from an S3 bucket and returning it as a string. Note that all initialization arguments can optionally be provided or overwritten at runtime.

[API Reference](/api/unreleased/tasks/aws.html#prefect-tasks-aws-s3-s3downloadtask)

## S3Upload <Badge text="task"/>

Task for uploading string data (e.g., a JSON string) to an S3 bucket. Note that all initialization arguments can optionally be provided or overwritten at runtime.

[API Reference](/api/unreleased/tasks/aws.html#prefect-tasks-aws-s3-s3uploadtask)

## StepActivate <Badge text="task"/>

Task for triggering the execution of AWS Step Function workflows.

[API Reference](/api/unreleased/tasks/aws.html#stepactivate)
