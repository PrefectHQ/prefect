from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Optional

import typer

from ..credentials import AwsCredentials

app = typer.Typer()


def upload(
    bundle_path: Annotated[str, typer.Option(help="The path to the bundle to upload")],
    bucket_name: Annotated[
        str, typer.Argument(help="The name of the bucket to upload to")
    ],
    credentials_block_name: Annotated[
        Optional[str], typer.Argument(help="The ID of the credentials block to use")
    ] = None,
    bucket_path: Annotated[
        Optional[str], typer.Argument(help="The path to upload the bundle to")
    ] = None,
):
    if credentials_block_name:
        credentials_block = AwsCredentials.load(credentials_block_name)
        if TYPE_CHECKING:
            assert isinstance(credentials_block, AwsCredentials)
    else:
        credentials_block = AwsCredentials()

    s3_client = credentials_block.get_s3_client()

    if bucket_path:
        key = str(Path(bucket_path) / Path(bundle_path).name)
    else:
        key = str(Path(bundle_path).name)

    s3_client.upload_file(Bucket=bucket_name, Key=key, Filename=bundle_path)


if __name__ == "__main__":
    typer.run(upload)
