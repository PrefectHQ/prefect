"""Generate CLI documentation."""  # noqa: INP001

from __future__ import annotations

import inspect
import logging
import warnings
from pathlib import Path
from typing import TypedDict

import click
import typer
from click import Command, MultiCommand, Parameter
from griffe import (
    Docstring,
    DocstringSection,
    DocstringSectionExamples,
)
from jinja2 import Environment, FileSystemLoader, select_autoescape

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
    # Storing "option" params. If you don't need them typed as click.Option,
    # "Parameter" is enough to capture both options/arguments in general.
    opts: list[Parameter]
    examples: list[str]
    epilog: str | None
    commands: list[CommandSummaryDict]
    subcommands: list[BuildDocsContext]


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


def build_docs_context(
    *,
    obj: Command,
    ctx: click.Context,
    indent: int = 0,
    name: str = "",
    call_prefix: str = "",
) -> BuildDocsContext:
    """Build a command context for documentation generation.

    Args:
        obj: The Click command object to document
        ctx: The Click context
        indent: Indentation level for nested commands
        name: Override name for the command
        call_prefix: Prefix to add to command name

    Returns:
        A BuildDocsContext object

    """
    # Command name can be empty, so ensure we always end up with a string
    if call_prefix:
        command_name = f"{call_prefix} {obj.name or ''}".strip()
    else:
        command_name = name if name else (obj.name or "")

    title: str = f"`{command_name}`" if command_name else "CLI"
    usage_pieces: list[str] = obj.collect_usage_pieces(ctx)

    args_list: list[ArgumentDict] = []
    opts_list: list[Parameter] = []

    # Collect arguments vs. options (skip the built-in help option)
    for param in obj.get_params(ctx):
        # If the parameter is an Option and its opts include '--help', skip it.
        if isinstance(param, click.Option) and "--help" in param.opts:
            continue

        help_record = param.get_help_record(ctx)  # Optional[tuple[str, str]]
        if help_record is not None:
            param_name, param_help = help_record
            if getattr(param, "param_type_name", "") == "argument":
                args_list.append({"name": param_name, "help": param_help})
            elif getattr(param, "param_type_name", "") == "option":
                opts_list.append(param)

    commands_list: list[CommandSummaryDict] = []
    subcommands: list[BuildDocsContext] = []

    # Only MultiCommand objects have subcommands
    if isinstance(obj, MultiCommand):
        all_commands: list[str] = obj.list_commands(ctx)
        # Filter out help commands and blocked commands
        blocked_commands = {"help", "--help", "deploy", "cloud"}
        filtered_commands: list[str] = [
            cmd for cmd in all_commands if cmd not in blocked_commands
        ]
        for command in filtered_commands:
            command_obj = obj.get_command(ctx, command)
            assert command_obj, f"Command {command} not found in {obj.name}"  # noqa: S101
            # Prepare a short "summary" for listing
            cmd_name = command_obj.name or ""
            cmd_help = command_obj.get_short_help_str()
            commands_list.append({"name": cmd_name, "help": cmd_help})

        # Recursively build docs for each subcommand
        for command in filtered_commands:
            command_obj = obj.get_command(ctx, command)
            assert command_obj  # noqa: S101
            sub_ctx = build_docs_context(
                obj=command_obj,
                ctx=ctx,
                indent=indent + 1,
                name="",  # Let the function pick the name from command_obj
                call_prefix=command_name,
            )
            subcommands.append(sub_ctx)

    return BuildDocsContext(
        indent=indent,
        command_name=command_name,
        title=title,
        help=get_help_text(obj.help or ""),
        examples=get_examples(obj.help or ""),
        usage_pieces=usage_pieces,
        args=args_list,
        opts=opts_list,
        epilog=obj.epilog,  # Optional[str]
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

    def store_code_block(match):
        code_blocks.append(match.group(0))
        return f"__CODE_BLOCK_{len(code_blocks) - 1}__"

    text = re.sub(code_block_pattern, store_code_block, text)

    # Also preserve inline code (single backticks)
    inline_code = []
    inline_code_pattern = r"`[^`]+`"

    def store_inline_code(match):
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
        f.write(rendered)

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
        f.write(content)


def get_docs_for_click(
    *,
    obj: click.Command,
    ctx: click.Context,
    indent: int = 0,
    name: str = "",
    call_prefix: str = "",
) -> str:
    """Build the top-level docs context & generate one MDX file per subcommand.

    Args:
        obj: The Click command object to document
        ctx: The Click context
        indent: Indentation level for nested commands
        name: Override name for the command
        call_prefix: Prefix to add to command name
        title: Override title for the command

    Returns:
        Empty string (files are written to disk)

    """
    docs_context = build_docs_context(
        obj=obj,
        ctx=ctx,
        indent=indent,
        name=name,
        call_prefix=call_prefix,
    )

    # Create the Jinja environment
    env = Environment(
        loader=FileSystemLoader("./scripts/templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["escape_mdx"] = escape_mdx

    # Where to store the generated MDX files
    cli_dir = "./docs/v3/api-ref/cli"

    # The top-level context is for "prefect" itself,
    # so docs_context["subcommands"] are each top-level subcommand.
    for sub_ctx in docs_context["subcommands"]:
        write_subcommand_docs(sub_ctx, env, cli_dir)

    return ""


if __name__ == "__main__":
    with warnings.catch_warnings():
        from prefect.cli.root import app

        # Convert a Typer app to a Click command object.
        click_obj: click.Command = typer.main.get_command(app)
        # Create a click.Context for it.
        main_ctx: click.Context = click.Context(click_obj)
        get_docs_for_click(obj=click_obj, ctx=main_ctx)
