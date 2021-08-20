from typing_extensions import Literal

from prefect.orion.utilities.schemas import PrefectBaseModel


DataSchemes = Literal["s3", "file"]


class DataLocation(PrefectBaseModel):
    name: str
    scheme: DataSchemes = "file"
    base_path: str = "/tmp"


class DataDocument(PrefectBaseModel):
    encoding: str
    blob: bytes
