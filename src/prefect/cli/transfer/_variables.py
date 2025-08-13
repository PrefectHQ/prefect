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
    results = {
        "succeeded": [],
        "failed": [],
        "skipped": [],
    }

    for variable in variables:
        try:
            # Check if variable already exists
            existing = None
            try:
                existing = await to_client.read_variable_by_name(variable.name)
            except Exception:
                # Variable doesn't exist, we can create it
                pass

            if existing:
                results["skipped"].append(
                    {
                        "name": variable.name,
                        "reason": "already exists",
                    }
                )
                continue

            # Create the variable in the target
            await to_client.create_variable(
                variable=Variable(
                    name=variable.name,
                    value=variable.value,
                    tags=variable.tags if hasattr(variable, "tags") else [],
                )
            )

            results["succeeded"].append(
                {
                    "name": variable.name,
                }
            )

        except Exception as e:
            results["failed"].append(
                {
                    "name": variable.name,
                    "error": str(e),
                }
            )

    return results
