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
        scheme=settings.orion.data.scheme.lower(),
    )


async def write_blob(blob: bytes, scheme: str, path: str) -> bool:
    full_path = f"{scheme}://{path}"
    with fsspec.open(full_path, mode="wb") as fp:
        fp.write(blob)

    return True


async def read_blob(scheme: str, path: str) -> bytes:
    full_path = f"{scheme}://{path}"
    with fsspec.open(full_path) as fp:
        blob = fp.read()

    return blob


async def resolve_orion_datadoc(datadoc: DataDocument) -> DataDocument:
    """
    Convert an orion datadoc to a user datadoc
    """
    if datadoc.encoding == "orion":
        # All orion data documents have a nested data document
        return await resolve_orion_datadoc(DataDocument.parse_raw(datadoc.blob))

    if datadoc.encoding in ["s3", "file"]:
        # The datadoc should contain a path to read a nested data document from
        path = datadoc.blob.decode()
        blob = await read_blob(datadoc.encoding, path)
        return await resolve_orion_datadoc(DataDocument.parse_raw(blob))

    # The datadoc is no longer resolvable by Orion, return it
    return datadoc
