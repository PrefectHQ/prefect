from rich.highlighter import RegexHighlighter

from prefect.states import StateType


class LevelHighlighter(RegexHighlighter):
    """Apply style to log levels."""

    base_style = "level."
    highlights: list[str] = [
        r"(?P<debug_level>DEBUG)",
        r"(?P<info_level>INFO)",
        r"(?P<warning_level>WARNING)",
        r"(?P<error_level>ERROR)",
        r"(?P<critical_level>CRITICAL)",
    ]


class UrlHighlighter(RegexHighlighter):
    """Apply style to urls."""

    base_style = "url."
    highlights: list[str] = [
        r"(?P<web_url>(https|http|ws|wss):\/\/[0-9a-zA-Z\$\-\_\+\!`\(\)\,\.\?\/\;\:\&\=\%\#]*)",
        r"(?P<local_url>(file):\/\/[0-9a-zA-Z\$\-\_\+\!`\(\)\,\.\?\/\;\:\&\=\%\#]*)",
    ]


class NameHighlighter(RegexHighlighter):
    """Apply style to names."""

    base_style = "name."
    highlights: list[str] = [
        # ?i means case insensitive
        # ?<= means find string right after the words: flow run
        r"(?i)(?P<flow_run_name>(?<=flow run) \'(.*?)\')",
        r"(?i)(?P<flow_name>(?<=flow) \'(.*?)\')",
        r"(?i)(?P<task_run_name>(?<=task run) \'(.*?)\')",
        r"(?i)(?P<task_name>(?<=task) \'(.*?)\')",
    ]


class StateHighlighter(RegexHighlighter):
    """Apply style to states."""

    base_style = "state."
    highlights: list[str] = [
        rf"(?P<{state.lower()}_state>{state.title()})" for state in StateType
    ] + [
        r"(?P<cached_state>Cached)(?=\(type=COMPLETED\))"  # Highlight only "Cached"
    ]


class PrefectConsoleHighlighter(RegexHighlighter):
    """Applies style from multiple highlighters."""

    base_style = "log."
    highlights: list[str] = (
        LevelHighlighter.highlights
        + UrlHighlighter.highlights
        + NameHighlighter.highlights
        + StateHighlighter.highlights
    )
