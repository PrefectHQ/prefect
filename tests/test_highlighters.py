import pytest
from rich.text import Span, Text

from prefect.logging.highlighters import (
    LevelHighlighter,
    NameHighlighter,
    UrlHighlighter,
)


@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_highlight_level(level):
    text = Text(f"10:21:34.114 | {level}    | Flow run 'polite-jackal' - Hello Marvin!")
    highlighter = LevelHighlighter()
    highlighter.highlight(text)
    assert text.spans == [
        Span(15, 15 + len(level), f"level.{level.lower()}_level"),
    ]


@pytest.mark.parametrize("kind", ["web_url", "local_url"])
def test_highlight_url(kind):
    url = "https://www.prefect.io/" if kind == "web_url" else "file://tests.py"
    text = Text(f"10:21:34.114 | INFO    | Flow run 'polite-jackal' - {url}")
    highlighter = UrlHighlighter()
    highlighter.highlight(text)
    assert text.spans == [
        Span(52, 52 + len(url), f"url.{kind}"),
    ]


@pytest.mark.parametrize(
    "name", ["flow_run_name", "flow_name", "task_run_name", "task_name"]
)
@pytest.mark.parametrize("lower", [True, False])
def test_highlight_name(name, lower):
    keyword = " ".join(name.split("name")).strip().rstrip("_")
    keyword = keyword.lower() if lower else keyword.upper()
    text = Text(f"10:21:34.114 | INFO    | {keyword} 'polite-jackal'")
    print(text)
    highlighter = NameHighlighter()
    highlighter.highlight(text)
    assert text.spans == [
        Span(26 + len(keyword), 41 + len(keyword), f"name.{name}"),
    ]
