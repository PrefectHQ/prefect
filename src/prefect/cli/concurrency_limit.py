"""
Command line interface for working with deployments.
"""
import sys
from pathlib import Path
from typing import List

import fastapi
import httpx
import pendulum
import typer
from rich.padding import Padding
from rich.pretty import Pretty
from rich.traceback import Traceback

from prefect.cli.base import app, console, exit_with_error
from prefect.client import OrionClient

from prefect.exceptions import FlowScriptError
from prefect.orion.schemas.filters import FlowFilter
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
