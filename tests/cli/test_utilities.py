import ast
import io
import json
from pathlib import Path

import pytest
from rich.console import Console

import prefect.cli
import prefect.cli._app as _cli
from prefect.cli._utilities import exit_with_error, print_verbatim

CLI_SOURCE_DIR = Path(prefect.cli.__file__).parent


@pytest.fixture
def captured_console(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    buffer = io.StringIO()
    monkeypatch.setattr(
        _cli, "console", Console(file=buffer, width=20, color_system=None)
    )
    return buffer


@pytest.mark.parametrize(
    "value",
    [
        "[bold]literal[/bold]",
        ":smile:",
        "literal [/unexpected]",
        "x" * 1000,
    ],
)
def test_print_verbatim_preserves_json_output(
    captured_console: io.StringIO, value: str
):
    payload = json.dumps({"value": value, "nested": [{"value": value}]}, indent=2)

    print_verbatim(payload)

    assert captured_console.getvalue() == payload + "\n"
    assert json.loads(captured_console.getvalue()) == {
        "value": value,
        "nested": [{"value": value}],
    }


@pytest.mark.parametrize(
    "message",
    ["Unknown setting name 'foo[/x]'.", "[bold]literal[/bold]"],
)
def test_exit_with_error_prints_message_literally(
    captured_console: io.StringIO, message: str
):
    with pytest.raises(SystemExit) as exc_info:
        exit_with_error(message, soft_wrap=True)

    assert exc_info.value.code == 1
    assert captured_console.getvalue() == message + "\n"


def test_exit_with_error_renders_markup_when_requested(
    captured_console: io.StringIO,
):
    with pytest.raises(SystemExit):
        exit_with_error("[bold]styled[/bold]", markup=True)

    assert captured_console.getvalue() == "styled\n"


def _is_serialized_output(node: ast.expr) -> bool:
    if isinstance(node, (ast.Constant, ast.JoinedStr)):
        return False
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Pretty"
    ):
        return False
    source = ast.unparse(node).lower()
    return "json" in source or "dump" in source


def test_cli_serialized_output_uses_print_verbatim():
    """
    JSON/YAML output printed via `console.print` is parsed for Rich markup and
    emoji aliases, which rewrites user data. Use `print_verbatim` instead.
    """
    offenders: list[str] = []
    for path in sorted(CLI_SOURCE_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "print"
                and "console" in ast.unparse(node.func.value)
                and node.args
                and _is_serialized_output(node.args[0])
            ):
                offenders.append(
                    f"{path.relative_to(CLI_SOURCE_DIR)}:{node.lineno}: "
                    f"{ast.unparse(node)}"
                )

    assert not offenders, (
        "Print serialized CLI output with `print_verbatim`:\n" + "\n".join(offenders)
    )
