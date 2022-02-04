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
    def __init__(self, blockdata):
        self.blockdata = blockdata
        self.datadoc = None

    def basepath(self):
        return Path(TemporaryDirectory().name)

    async def write(self, data):
        storage_path = str(self.basepath() / str(uuid4()))
        self.datadoc = DataDocument.encode(
            encoding="file", data=data, path=storage_path
        )

    async def read(self):
        return self.datadoc.decode()


@register_blockapi("orionstorage-block")
class OrionStorageBlock(BlockAPI):
    from prefect.client import OrionClient

    def __init__(self, blockdata):
        self.blockdata = blockdata
        self.datadoc = None

    async def write(self, data):
        async with OrionClient() as client:
            response = await client.post("/data/persist", content=data)
            self.datadoc = DataDocument.parse_obj(response.json())

    async def read(self):
        if self.datadoc is None:
            raise RuntimeError
        if self.datadoc.has_cached_data():
            return self.datadoc.decode()

        async with OrionClient() as client:
            response = await client.post(
                "/data/retrieve", json=self.datadoc.dict(json_compatible=True)
            )
            return response.content
