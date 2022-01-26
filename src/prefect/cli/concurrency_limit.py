"""
Command line interface for working with concurrency limits.
"""
import httpx
import typer
from rich.pretty import Pretty

from prefect.cli.base import app, console
from prefect.client import OrionClient

from prefect.utilities.asyncio import sync_compatible

concurrency_limit_app = typer.Typer(name="concurrency-limit")
app.add_typer(concurrency_limit_app)


@concurrency_limit_app.command()
@sync_compatible
async def create(tag: str, concurrency_limit: int):

    async with OrionClient() as client:
        try:
            cl = await client.create_concurrency_limit(
                tag=tag, concurrency_limit=concurrency_limit
            )
        except httpx.HTTPStatusError as exc:
            raise

    console.print(Pretty(cl))


@concurrency_limit_app.command()
@sync_compatible
async def read(tag: str):

    async with OrionClient() as client:
        try:
            result = await client.read_concurrency_limit_by_tag(tag=tag)
        except httpx.HTTPStatusError as exc:
            raise

    console.print(Pretty(result))


@concurrency_limit_app.command()
@sync_compatible
async def ls(limit: int = 15, offset: int = 0):

    async with OrionClient() as client:
        try:
            result = await client.read_concurrency_limits(limit=limit, offset=offset)
        except httpx.HTTPStatusError as exc:
            raise

    console.print(Pretty(result))


@concurrency_limit_app.command()
@sync_compatible
async def delete(tag: str):

    async with OrionClient() as client:
        try:
            result = await client.delete_concurrency_limit_by_tag(tag=tag)
        except httpx.HTTPStatusError as exc:
            raise

    if result:
        console.print(Pretty(f"Deleted concurrency limit set on the tag: {tag}"))
    else:
        console.print(Pretty(f"No concurrency limit found for the tag: {tag}"))
