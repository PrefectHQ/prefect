import pytest
from rich.text import Span, Text

from prefect.logging.highlighters import (
    LevelHighlighter,
    NameHighlighter,
    PrefectConsoleHighlighter,
    StateHighlighter,
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


@pytest.mark.parametrize("url_kind", ["web", "local"])
def test_highlight_url(url_kind):
    url = "https://www.prefect.io/" if url_kind == "web" else "file://tests.py"
    text = Text(f"10:21:34.114 | INFO    | Flow run 'polite-jackal' - {url}")
    highlighter = UrlHighlighter()
    highlighter.highlight(text)
    assert text.spans == [
        Span(52, 52 + len(url), f"url.{url_kind}_url"),
    ]


@pytest.mark.parametrize("name", ["flow_run", "flow", "task_run", "task"])
@pytest.mark.parametrize("lower", [True, False])
def test_highlight_name(name, lower):
    keyword = name.replace("_", " ").strip()
    keyword = keyword.lower() if lower else keyword.upper()
    text = Text(f"10:21:34.114 | INFO    | {keyword} 'polite-jackal'")
    highlighter = NameHighlighter()
    highlighter.highlight(text)
    assert text.spans == [
        Span(25 + len(keyword), 41 + len(keyword), f"name.{name}_name"),
    ]


@pytest.mark.parametrize(
    "state", ["completed", "cancelled", "failed", "crashed", "cached"]
)
def test_highlight_state(state):
    if state == "cached":
        text = Text(
            "Flow run 'polite-jackal' - Finished in state Cached(type=COMPLETED)"
        )
        expected_span = Span(
            45, 51, "state.cached_state"
        )  # Only "Cached" is highlighted
    else:
        keyword = state.title()
        text = Text(f"Flow run 'polite-jackal' - Finished in state {keyword}()")
        expected_span = Span(45, 45 + len(keyword), f"state.{state}_state")

    highlighter = StateHighlighter()
    highlighter.highlight(text)
    assert text.spans == [expected_span]


def test_highlight_console():
    text = Text(
        "10:21:34.114 | INFO    | Flow run 'polite-jackal' - Finished in state"
        " Completed()"
    )
    highlighter = PrefectConsoleHighlighter()
    highlighter.highlight(text)
    assert text.spans == [
        Span(15, 19, "log.info_level"),
        Span(33, 49, "log.flow_run_name"),
        Span(70, 79, "log.completed_state"),
    ]
