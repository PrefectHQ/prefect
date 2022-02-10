import io

from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from typing import Optional
from prefect.blocks.core import BlockAPI, register_blockapi
from prefect.orion.schemas.data import DataDocument


@register_blockapi("s3storage-block")
class S3Block(BlockAPI):
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    profile_name: Optional[str] = None
    region_name: Optional[str] = None
    bucket: str

    def block_initialization(self):
        import boto3

        self.aws_session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            profile_name=self.profile_name,
            region_name=self.region_name,
        )

    async def write(self, data: bytes):
        import boto3

        s3_client = self.aws_session.client("s3")
        stream = io.BytesIO(data)
        data_location = {"Bucket": self.bucket, "Key": str(uuid4())}
        s3_client.upload_fileobj(stream, **data_location)
        return DataDocument.encode(encoding="json", data=data_location)

    async def read(self, datadoc):
        import boto3

        s3_client = self.aws_session.client("s3")
        data_location = datadoc.decode()
        stream = io.BytesIO()
        s3_client.download_fileobj(**data_location)
        stream.seek(0)
        output = stream.read()
        return output


@register_blockapi("localstorage-block")
class LocalStorageBlock(BlockAPI):
    def block_initialization(self) -> None:
        pass

    def basepath(self):
        # return Path(TemporaryDirectory().name)
        return Path("/tmp/localstorageblock")

    async def write(self, data):
        storage_path = str(self.basepath() / str(uuid4()))
        return DataDocument.encode(encoding="file", data=data, path=storage_path)

    async def read(self, datadoc):
        return datadoc.decode()


@register_blockapi("orionstorage-block")
class OrionStorageBlock(BlockAPI):
    def block_initialization(self) -> None:
        pass

    async def write(self, data):
        from prefect.client import OrionClient

        async with OrionClient() as client:
            response = await client.post("/data/persist", content=data)
            return DataDocument.parse_obj(response.json())

    async def read(self, datadoc):
        from prefect.client import OrionClient

        if datadoc is None:
            raise RuntimeError
        if datadoc.has_cached_data():
            return datadoc.decode()

        async with OrionClient() as client:
            response = await client.post(
                "/data/retrieve", json=datadoc.dict(json_compatible=True)
            )
            return response.content
