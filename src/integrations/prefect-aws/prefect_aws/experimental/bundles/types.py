from typing import Annotated

import typer

S3Bucket = Annotated[str, typer.Option("--bucket")]
S3Key = Annotated[str, typer.Option("--key")]
AwsCredentialsBlockName = Annotated[str, typer.Option("--aws-credentials-block-name")]
LocalFilepath = Annotated[str, typer.Argument()]
