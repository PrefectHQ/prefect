import datetime
from functools import wraps
from typing import Any, Callable, Dict, Iterable, Optional, Union

import boto3
from prefect.context import FlowRunContext, TaskRunContext
from prefect.task_runners import BaseTaskRunner, SequentialTaskRunner
from prefect.tasks import task
from pydantic import BaseModel


class BlockData(BaseModel):
    data: dict
    blockref: str


def register_blockapi(blockref):
    pass


def assemble_block(blockdata):
    block = BlockRegistry.get(blockdata.blockref)
    return block(blockdata)


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

    def write(self, context, data):
        s3_key = f"s3://{self.blockdata.bucket}/{self.path_template(context)}"
        # serialize and write data
        # return datadoc with s3 key

    def read(self, path_datadoc):
        s3_key = path_datadoc.read()
        # read data from path


@register_blockapi("localstorage-block")
class LocalStorageBlock(BlockAPI):
    def __init__(self, blockdata):
        self.blockdata = blockdata

    def path_template(self):
        template = string.Template(self.data.path_template)
        # add template substitutions here

    def write(self, context, data):
        storage_path = f"{self.blockdata.basedir}/{self.path_template(context)}"
        # serialize and write data
        # return datadoc with storage path

    def read(self, path_datadoc):
        storage_path = path_datadoc.decode()
        # read data from path
