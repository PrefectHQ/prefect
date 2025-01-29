"""Exposes the typer app directly within the package, enabling the use-case of using
`python -m prefect` in addition to the existing `prefect` console_scripts entrypoint.

This is required to i.e. run prefect natively in PyCharm with debugger or simplifies running the CLI from within a
python script.
"""
from .cli import app

if __name__ == "__main__":
    app()
