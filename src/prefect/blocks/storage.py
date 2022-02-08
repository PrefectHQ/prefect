# import boto3

from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from prefect.blocks.core import BlockAPI, register_blockapi
from prefect.orion.schemas.data import DataDocument


@register_blockapi("s3storage-block")
class S3Block(BlockAPI):
    def __init__(self, blockdata):
        self.blockdata = blockdata
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=self.blockdata.aws_access_key_id,
            aws_secret_access_key=self.blockdata.aws_secret_access_key,
            profile_name=self.blockdata.profile_name,
            region_name=self.blockdata.region_name,
        )

    def basepath(self):
        return self.blockdata.basepath

    async def write(self, data):
        # embed datadoc that stores the s3 key on the block
        pass

    async def read(self):
        # retrieve s3 key from enbedded datadoc and read
        pass


@register_blockapi("localstorage-block")
class LocalStorageBlock(BlockAPI):
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
