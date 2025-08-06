import re
from typing import AsyncIterator

import anyio
from slugify import slugify

_REPO_ROOT = anyio.Path(__file__).parent.parent
_EXAMPLES_DIR = _REPO_ROOT / "examples"
_MDX_EXAMPLES_DIR = _REPO_ROOT / "docs" / "v3" / "examples"
_RE_NEWLINE = re.compile(r"\r?\n")
_RE_FRONTMATTER = re.compile(r"^---$", re.MULTILINE)
_GITHUB_BASE_URL = "https://github.com/PrefectHQ/prefect/blob/main/examples/"


async def get_example_paths() -> AsyncIterator[anyio.Path]:
    async for file in _EXAMPLES_DIR.iterdir():
        if await file.is_file() and file.suffix == ".py":
            yield file


async def convert_example_to_mdx_page(example_path: anyio.Path) -> str:
    """Render a Python code example to Markdown documentation format."""

    content = await example_path.read_text()

    lines = _RE_NEWLINE.split(content)
    markdown: list[str] = []
    code: list[str] = []
    for line in lines:
        if line == "#" or line.startswith("# "):
            if code:
                markdown.extend(["```python", *code, "```", ""])
                code = []
            markdown.append(line[2:])
        else:
            if markdown and markdown[-1]:
                markdown.append("")
            if code or line:
                code.append(line)

    if code:
        markdown.extend(["```python", *code, "```", ""])

    text = "\n".join(markdown)
    if _RE_FRONTMATTER.match(text):
        # Strip out frontmatter from text.
        if match := _RE_FRONTMATTER.search(text, 4):
            github_url = f"{_GITHUB_BASE_URL}{example_path.relative_to(_REPO_ROOT)}"

            # Using raw HTML for precise placement; most Markdown/MDX renderers will
            # preserve the styling while allowing fallback to a plain link if HTML
            # is stripped.
            github_button = (
                f'<a href="{github_url}" target="_blank">View on GitHub</a>\n\n'
            )

            frontmatter = "---\n"

            for line in text[: match.end()].split("\n"):
                if line.startswith(("title:", "description:", "icon:", "keywords:")):
                    frontmatter += line + "\n"

            frontmatter += "---\n\n"

            # Insert the button at the very top of the document.
            text = frontmatter + github_button + text[match.end() + 1 :]

    return text


async def main() -> None:
    async for example_path in get_example_paths():
        text = await convert_example_to_mdx_page(example_path)
        destination_path = _MDX_EXAMPLES_DIR / f"{slugify(example_path.stem)}.mdx"
        await destination_path.write_text(text)


if __name__ == "__main__":
    anyio.run(main)
