"""
Command line interface for working with profiles
"""
from typing import List

import toml

import prefect.context
import prefect.settings
from prefect.cli.base import (
    PrefectTyper,
    app,
    console,
    exit_with_error,
    exit_with_success,
)

profile_app = PrefectTyper(
    name="profile", help="Commands for interacting with profiles."
)
app.add_typer(profile_app)


@profile_app.command()
def inspect():
    """
    View settings in the current profile.

    Use `prefect --profile <name> profile inspect` to get settings for another profile.
    """
    profile = prefect.context.get_profile_context()
    name, env = profile.name, profile.env
    console.out(toml.dumps({name: env}).strip())


@profile_app.command()
def ls():
    """
    List profile names.
    """
    profiles = toml.loads(prefect.settings.from_env().profiles_path.read_text())
    for name in profiles:
        console.print(name)


@profile_app.command()
def set(variables: List[str]):
    """
    Set a value in the current profile.
    """
    path = prefect.settings.from_env().profiles_path
    profiles = toml.loads(path.read_text())
    profile = prefect.context.get_profile_context()
    env = profiles[profile.name]

    parsed_variables = []
    for variable in variables:
        try:
            var, value = variable.split("=")
        except ValueError:
            exit_with_error(
                f"Failed to parse argument {variable!r}. Use the format 'VAR=VAL'."
            )

        parsed_variables.append((var, value))

    for var, value in parsed_variables:
        env[var] = value
        console.print(f"Set variable {var!r} to {value!r}")

    path.write_text(toml.dumps(profiles))

    exit_with_success(f"Updated profile {profile.name!r}")


@profile_app.command()
def unset(variables: List[str]):
    """
    Set a value in the current profile.
    """
    path = prefect.settings.from_env().profiles_path
    profiles = toml.loads(path.read_text())
    profile = prefect.context.get_profile_context()
    env = profiles[profile.name]

    for var in variables:
        if var not in env:
            exit_with_error(f"Variable {var!r} not found in profile {profile.name!r}.")
        env.pop(var)

    for var in variables:
        console.print(f"Unset variable {var!r}")

    path.write_text(toml.dumps(profiles))

    exit_with_success(f"Updated profile {profile.name!r}")
