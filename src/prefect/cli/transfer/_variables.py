"""
Variable transfer utilities for the transfer command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from prefect.cli.root import app

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import Variable


async def gather_variables(client: "PrefectClient") -> list["Variable"]:
    """
    Gather all variables from the source profile.
    """
    try:
        variables = await client.read_variables()
        return variables
    except Exception as e:
        app.console.print(f"[yellow]Warning: Could not read variables: {e}[/yellow]")
        return []


async def transfer_variables(
    variables: list["Variable"],
    to_client: "PrefectClient",
) -> dict[str, Any]:
    """
    Transfer variables to the target profile.

    Returns a dictionary with succeeded, failed, and skipped variables.
    """
    # TODO: Implement variable transfer
    # See IMPLEMENTATION_NOTES.md for details
    raise NotImplementedError(
        "Variable transfer not yet implemented. "
        "This should be straightforward as variables have no dependencies."
    )
