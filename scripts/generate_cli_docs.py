"""Generate CLI documentation."""

from __future__ import annotations

import inspect
import logging
import warnings
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypedDict

import cyclopts
from griffe import (
    Docstring,
    DocstringSection,
    DocstringSectionExamples,
)
from jinja2 import Environment, FileSystemLoader, select_autoescape

from prefect.cli._app import _app

logging.getLogger("griffe.docstrings.google").setLevel(logging.ERROR)


class ArgumentDict(TypedDict):
    """A dictionary representing a command argument."""

    name: str
    help: str


class CommandSummaryDict(TypedDict):
    """A dictionary representing a command summary."""

    name: str
    help: str


class BuildDocsContext(TypedDict):
    """A dictionary representing a command context."""

    indent: int
    command_name: str
    title: str
    help: list[DocstringSection]
    usage_pieces: list[str]
    args: list[ArgumentDict]
    opts: list[Any]
    examples: list[str]
    epilog: str | None
    commands: list[CommandSummaryDict]
    subcommands: list["BuildDocsContext"]


def get_help_text(docstring_object: str) -> list[DocstringSection]:
    """Get help text sections from a docstring.

    Args:
        docstring_object: The docstring to parse.

    Returns:
        list of docstring text sections.

    """
    return [
        section
        for section in Docstring(inspect.cleandoc(docstring_object), lineno=1).parse(
            "google",
            warnings=False,
        )
        if section.kind == "text"
    ]


def get_examples(docstring_object: str) -> list[str]:
    """Get example strings from a docstring.

    Args:
        docstring_object: The docstring to parse.

    Returns:
        list of example strings.

    """
    return [
        text
        for section in Docstring(inspect.cleandoc(docstring_object), lineno=1).parse(
            "google",
            warnings=False,
        )
        if isinstance(section, DocstringSectionExamples)
        for _, text in section.value
    ]


def _parameter_is_option(meta: cyclopts.Parameter | None) -> bool:
    """Return True if the parameter should be rendered as an option."""
    return meta is not None and bool(meta.name) and meta.name[0].startswith("-")


def _positional_display_name(
    param_name: str,
    meta: cyclopts.Parameter | None,
) -> str:
    """Derive the display name for a positional argument."""
    if meta is not None and meta.name and not meta.name[0].startswith("-"):
        return meta.name[0].upper()
    return param_name.upper()


def _extract_command_params(
    app: cyclopts.App,
) -> tuple[list[Any], list[Any], list[str], list[str]]:
    """Extract options, arguments, and usage hints from a Cyclopts App command.

    Returns:
        A tuple of (options, arguments, required_positional_names,
        optional_positional_names).

    """
    options: list[Any] = []
    arguments: list[Any] = []
    required_positional: list[str] = []
    optional_positional: list[str] = []

    if app.default_command is None:
        return options, arguments, required_positional, optional_positional

    signature = inspect.signature(app.default_command)
    try:
        type_hints = inspect.get_annotations(
            app.default_command,
            eval_str=True,
        )
    except Exception:
        type_hints = {}

    for param_name, param in signature.parameters.items():
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        annotation = type_hints.get(param_name, param.annotation)
        meta: cyclopts.Parameter | None = None
        if hasattr(annotation, "__metadata__"):
            for item in annotation.__metadata__:
                if isinstance(item, cyclopts.Parameter):
                    meta = item
                    break

        # Public positional arguments hidden from `--help` (e.g. the `name`
        # argument to `prefect automation inspect`) are still accepted and
        # should be documented. Internal parameters such as the root `*tokens`
        # argument are filtered by kind above.
        help_text = (meta.help if meta is not None and meta.help else "") or ""

        if _parameter_is_option(meta):
            if meta is not None and meta.show is False:
                continue
            options.append(
                SimpleNamespace(
                    opts=meta.name,
                    help=help_text,
                )
            )
        else:
            display_name = _positional_display_name(param_name, meta)
            is_required = param.default is inspect.Parameter.empty
            arguments.append(
                SimpleNamespace(
                    name=display_name,
                    help=help_text,
                    required=is_required,
                )
            )
            if is_required:
                required_positional.append(display_name)
            else:
                optional_positional.append(display_name)

    return options, arguments, required_positional, optional_positional


def build_docs_context(
    app: cyclopts.App,
    name: str,
    call_prefix: str = "",
    indent: int = 1,
) -> BuildDocsContext:
    """Build a command context for documentation generation from a Cyclopts App.

    Args:
        app: The Cyclopts App to document.
        name: The command name to use for this level (e.g. the alias key).
        call_prefix: The parent command path used to build the full command name.
        indent: The Markdown heading level for this command.

    Returns:
        A BuildDocsContext object.

    """
    command_name = f"{call_prefix} {name}".strip()
    title = f"`{command_name}`" if command_name else "CLI"

    if app.default_command is not None and app.default_command.__doc__:
        docstring = app.default_command.__doc__
    else:
        docstring = app.help or ""

    options, arguments, required_positional, optional_positional = (
        _extract_command_params(app)
    )

    if app._registered_commands:
        usage_pieces = ["[OPTIONS]", "COMMAND", "[ARGS]..."]
    elif app.default_command is not None:
        usage_pieces = ["[OPTIONS]"]
        usage_pieces.extend(required_positional)
        usage_pieces.extend(f"[{name}]" for name in optional_positional)
    else:
        usage_pieces = ["[OPTIONS]"]

    commands_list: list[CommandSummaryDict] = []
    subcommands: list[BuildDocsContext] = []

    for sub_name, sub_app in app._registered_commands.items():
        commands_list.append(
            {"name": sub_name, "help": sub_app.help or ""},
        )
        subcommands.append(
            build_docs_context(
                sub_app,
                name=sub_name,
                call_prefix=command_name,
                indent=indent + 1,
            )
        )

    return BuildDocsContext(
        indent=indent,
        command_name=command_name,
        title=title,
        help=get_help_text(docstring),
        examples=get_examples(docstring),
        usage_pieces=usage_pieces,
        args=arguments,
        opts=options,
        epilog=None,
        commands=commands_list,
        subcommands=subcommands,
    )


def escape_mdx(text: str) -> str:
    """Escape characters that commonly break MDX (Mintlify).

    - Replace angle brackets < >
    - Replace curly braces { }
    - Escape backticks, pipes, and arrow functions
    - Escape dollar signs to avoid template interpolation.
    """
    import re

    if not text:
        return ""

    # First, let's preserve code blocks by temporarily replacing them
    # This regex matches triple backtick code blocks
    code_blocks = []
    code_block_pattern = r"```[\s\S]*?```"

    def store_code_block(match: re.Match[str]) -> str:
        code_blocks.append(match.group(0))
        return f"__CODE_BLOCK_{len(code_blocks) - 1}__"

    text = re.sub(code_block_pattern, store_code_block, text)

    # Also preserve inline code (single backticks)
    inline_code = []
    inline_code_pattern = r"`[^`]+`"

    def store_inline_code(match: re.Match[str]) -> str:
        inline_code.append(match.group(0))
        return f"__INLINE_CODE_{len(inline_code) - 1}__"

    text = re.sub(inline_code_pattern, store_inline_code, text)

    # Escape < and >
    text = text.replace("<", "&lt;").replace(">", "&gt;")

    # Escape { and }
    text = text.replace("{", "&#123;").replace("}", "&#125;")

    # Escape backticks (only those not in code blocks)
    text = text.replace("`", "\\`")

    # Escape pipes (especially in tables)
    text = text.replace("|", "\\|")

    # Escape => arrow
    text = re.sub(r"(?<!\w)=>(?!\w)", "\\=>", text)

    # Escape $
    text = text.replace("$", "\\$")

    # Escape ! at start of lines
    text = re.sub(r"(?m)^!", "\\!", text)

    # Restore code blocks
    for i, block in enumerate(code_blocks):
        text = text.replace(f"__CODE_BLOCK_{i}__", block)

    # Restore inline code
    for i, code in enumerate(inline_code):
        text = text.replace(f"__INLINE_CODE_{i}__", code)

    return text


def write_command_docs(
    command_context: BuildDocsContext,
    env: Environment,
    output_dir: str,
) -> None:
    """Render a single command (and do *not* recurse in the template).

    Then recurse here in Python for each subcommand.

    Args:
        command_context: Context containing command documentation
        env: Jinja environment for rendering templates
        output_dir: Directory to write output files

    """
    # 1. Render the Jinja template for this command only
    template = env.get_template("docs_template.jinja")
    rendered = template.render(command=command_context)

    # 2. Create a filename. For example, use the "command_name" field:
    #    Convert any spaces or slashes to underscores, etc.
    command_name_clean = command_context["command_name"].replace(" ", "_")
    if not command_name_clean:
        command_name_clean = "cli_root"  # fallback if top-level name is empty

    filename = f"{command_name_clean}.mdx"
    filepath = Path(output_dir) / filename

    # 3. Write out to disk
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    with Path.open(filepath, mode="w", encoding="utf-8") as f:
        f.write(rendered.rstrip() + "\n")

    # 4. Recursively render subcommands in the same manner
    for sub_ctx in command_context["subcommands"]:
        write_command_docs(sub_ctx, env, output_dir)


def render_command_and_subcommands(
    cmd_context: BuildDocsContext,
    env: Environment,
) -> str:
    """Render the given command then recurse in Python to render/append all subcommands.

    Args:
        cmd_context: Context containing command documentation
        env: Jinja environment for rendering templates

    Returns:
        Rendered documentation string

    """
    # 1) Render the "cmd_context" itself:
    template = env.get_template("docs_template.jinja")
    rendered = template.render(command=cmd_context)

    # 2) Recursively render each child subcommand and concatenate
    for sub_ctx in cmd_context["subcommands"]:
        sub_rendered = render_command_and_subcommands(sub_ctx, env)
        rendered += "\n\n" + sub_rendered

    return rendered


def write_subcommand_docs(
    top_level_sub: BuildDocsContext,
    env: Environment,
    output_dir: str,
) -> None:
    """Render one *top-level* and all nested subcommands into a single MDX file.

    Args:
        top_level_sub: Context containing top-level command documentation
        env: Jinja environment for rendering templates
        output_dir: Directory to write output files

    """
    content = render_command_and_subcommands(top_level_sub, env)

    # "command_name" might be something like "prefect artifact"
    # so let's extract the last token for the filename:
    name_parts = top_level_sub["command_name"].split()
    file_stub = name_parts[-1] if name_parts else "cli-root"  # e.g. "artifact"

    filename = f"{file_stub}.mdx"
    file_path = Path(output_dir) / filename
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    with Path.open(file_path, "w", encoding="utf-8") as f:
        f.write(content.rstrip() + "\n")


def generate_cli_docs(output_dir: str = "./docs/v3/api-ref/cli") -> None:
    """Generate MDX CLI documentation for the Prefect Cyclopts application."""
    env = Environment(
        loader=FileSystemLoader("./scripts/templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["escape_mdx"] = escape_mdx

    blocked_commands = {"--help", "deploy", "cloud"}
    for name, app in _app.resolved_commands().items():
        if name in blocked_commands:
            continue
        top_ctx = build_docs_context(app, name=name, call_prefix="", indent=1)
        write_subcommand_docs(top_ctx, env, output_dir)


if __name__ == "__main__":
    with warnings.catch_warnings():
        generate_cli_docs()
