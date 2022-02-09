"""
Command line interface for working with profiles
"""
from typing import List

import toml
import typer

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
    name="profile", help="Commands for interacting with the profile."
)
app.add_typer(profile_app)


def load_profiles() -> dict:
    path = prefect.settings.from_env().profiles_path
    return toml.loads(path.read_text())


def write_profiles(profiles: dict):
    path = prefect.settings.from_env().profiles_path
    return path.write_text(toml.dumps(profiles))


@profile_app.command()
def inspect(name: str = typer.Argument(None), all: bool = False):
    """
    View settings in a profile.
    """
    if all:
        profiles = load_profiles()
        console.out(toml.dumps(profiles).strip())
        return

    if name:
        profiles = load_profiles()
        if name not in profiles:
            exit_with_error(f"Profle {name!r} not found.")
        env = profiles[name]
    else:
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
    profiles = load_profiles()
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

    write_profiles(profiles)
    exit_with_success(f"Updated profile {profile.name!r}")


@profile_app.command()
def unset(variables: List[str]):
    """
    Set a value in the current profile.
    """
    profiles = load_profiles()
    profile = prefect.context.get_profile_context()
    env = profiles[profile.name]

    for var in variables:
        if var not in env:
            exit_with_error(f"Variable {var!r} not found in profile {profile.name!r}.")
        env.pop(var)

    for var in variables:
        console.print(f"Unset variable {var!r}")

    write_profiles(profiles)
    exit_with_success(f"Updated profile {profile.name!r}")


@profile_app.command()
def create(
    new_name: str,
    from_name: str = typer.Option(None, "--from", help="Copy an existing profile."),
):
    """
    Create a new profile
    """
    profiles = load_profiles()
    if new_name in profiles:
        exit_with_error(
            f"Profile {new_name!r} already exists. "
            f"Remove it with `prefect profile rm {new_name!r}'` first."
        )

    if from_name:
        if from_name not in profiles:
            exit_with_error("Profile {from_name!r} not found.")

        profiles[new_name] = profiles[from_name]
        from_blurb = f" matching {from_name!r}"
    else:
        from_blurb = ""
        profiles[new_name] = {}

    write_profiles(profiles)
    exit_with_success(f"Created profile {new_name!r}{from_blurb}.")


@profile_app.command()
def rm(name: str):
    """
    Delete the given profile.
    """
    profiles = load_profiles()
    if name not in profiles:
        exit_with_error(f"Profle {name!r} not found.")

    profiles.pop(name)

    verb = "Removed"
    if name == "default":
        verb = "Reset"
        profiles["default"] = {}

    write_profiles(profiles)
    exit_with_success(f"{verb} profile {name!r}.")
