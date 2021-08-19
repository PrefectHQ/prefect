import fsspec

from prefect import settings
from prefect.orion.schemas.data import DataDocument, DataLocation


def get_instance_data_location() -> DataLocation:
    """
    Return the current data location configured for this Orion instance
    """
    return DataLocation(
        name=settings.orion.data.name,
        base_path=settings.orion.data.base_path,
        credential_name=settings.orion.data.credential_name,
        scheme=settings.orion.data.scheme.lower(),
    )


async def write_datadoc_blob(datadoc: DataDocument, dataloc: DataLocation) -> bool:
    # Write the data document to the given location...
    if dataloc.scheme == "inline":
        return False

    with fsspec.open(datadoc.path, mode="wb") as fp:
        fp.write(datadoc.blob)

    return True


async def read_datadoc_blob(datadoc: DataDocument, dataloc: DataLocation) -> bytes:
    if dataloc.scheme == "inline":
        return datadoc.blob

    with fsspec.open(datadoc.path) as fp:
        return fp.read()
