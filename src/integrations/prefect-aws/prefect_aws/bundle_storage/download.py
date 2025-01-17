from typing import TYPE_CHECKING, Annotated, Optional

import typer

from ..credentials import AwsCredentials


def download(
    bucket_name: Annotated[
        str, typer.Option(help="The name of the bucket to upload to")
    ],
    key: Annotated[str, typer.Option(help="The key to download the bundle from")],
    credentials_block_name: Annotated[
        Optional[str], typer.Option(help="The name of the AWS credentials block to use")
    ] = None,
    local_path: Annotated[
        str, typer.Argument(help="The path to download the bundle to")
    ] = ".",
):
    if credentials_block_name:
        credentials_block = AwsCredentials.load(credentials_block_name)
        if TYPE_CHECKING:
            assert isinstance(credentials_block, AwsCredentials)
    else:
        credentials_block = AwsCredentials()
    s3_client = credentials_block.get_s3_client()
    s3_client.download_file(Bucket=bucket_name, Key=key, Filename=local_path)


if __name__ == "__main__":
    typer.run(download)
