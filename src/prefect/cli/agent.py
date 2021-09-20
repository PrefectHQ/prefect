import typer

from prefect.agent import run_agent
from prefect.cli.base import app, console
from prefect.utilities.asyncio import sync_compatible

agent_app = typer.Typer(name="agent")
app.add_typer(agent_app)


@agent_app.command()
@sync_compatible
async def start():
    console.print("Starting agent...")
    await run_agent()
    console.print("Agent stopped!")
