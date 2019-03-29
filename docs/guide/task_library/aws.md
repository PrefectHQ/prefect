---
title: AWS
---

# Amazon Web Services

A collection of tasks for interacting with AWS resources.

Note that all tasks require a Prefect Secret called `"AWS_CREDENTIALS"` which should be a JSON
document with two keys: `"ACCESS_KEY"` and `"SECRET_ACCESS_KEY"`.

## S3Download <Badge text="task"/>

Task for downloading data from an S3 bucket and returning it as a string. Note that all initialization arguments can optionally be provided or overwritten at runtime.

[API Reference](/api/unreleased/tasks/aws.html#prefect-tasks-aws-s3-s3downloadtask)

## S3Upload <Badge text="task"/>

Task for uploading string data (e.g., a JSON string) to an S3 bucket. Note that all initialization arguments can optionally be provided or overwritten at runtime.

[API Reference](/api/unreleased/tasks/aws.html#prefect-tasks-aws-s3-s3uploadtask)
