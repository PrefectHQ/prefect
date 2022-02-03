# import boto3

from prefect.blocks.core import BlockAPI, register_blockapi
from prefect.client import OrionClient

# from prefect.context import FlowRunContext, TaskRunContext
from prefect.orion.schemas.data import DataDocument

# from prefect.task_runners import BaseTaskRunner, SequentialTaskRunner
# from prefect.tasks import task


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

    def path_template(self):
        template = string.Template(self.data.path_template)
        # add template substitutions here

    def write(self, data):
        s3_key = f"s3://{self.blockdata.bucket}/{self.path_template(context)}"
        # serialize and write data
        # return datadoc with s3 key

    def read(self):
        s3_key = path_datadoc.read()
        # read data from path


@register_blockapi("localstorage-block")
class LocalStorageBlock(BlockAPI):
    def __init__(self, blockdata):
        self.blockdata = blockdata

    def path_template(self):
        template = string.Template(self.data.path_template)
        # add template substitutions here

    def write(self, data):
        storage_path = f"{self.blockdata.basedir}/{self.path_template(context)}"
        file_datadoc = DataDocument.encode(
            encoding="file", data=data, path=storage_path
        )

    def read(self):
        return file_datadoc.decode()


@register_blockapi("orionstorage-block")
class OrionStorageBlock(BlockAPI):
    def __init__(self, blockdata):
        self.blockdata = blockdata
        self.orion_datadoc = None

    async def write(self, data):
        async with OrionClient() as client:
            response = await client.post("/data/persist", content=data)
            self.orion_datadoc = DataDocument.parse_obj(response.json())

    async def read(self):
        if self.orion_datadoc is None:
            raise RuntimeError
        if self.orion_datadoc.has_cached_data():
            return self.orion_datadoc.decode()

        async with OrionClient() as client:
            response = await client.post(
                "/data/retrieve", json=self.orion_datadoc.dict(json_compatible=True)
            )
            return response.content
