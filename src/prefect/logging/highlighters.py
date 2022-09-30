from rich.highlighter import RegexHighlighter


class LevelHighlighter(RegexHighlighter):
    """Apply style to log levels."""

    base_style = "level."
    highlights = [
        r"(?P<debug_level>DEBUG)",
        r"(?P<info_level>INFO)",
        r"(?P<warning_level>WARNING)",
        r"(?P<error_level>ERROR)",
        r"(?P<critical_level>CRITICAL)",
    ]


class UrlHighlighter(RegexHighlighter):
    """Apply style to urls."""

    base_style = "url."
    highlights = [
        r"(?P<web_url>(https|http|ws|wss):\/\/[0-9a-zA-Z\$\-\_\+\!`\(\)\,\.\?\/\;\:\&\=\%\#]*)",
        r"(?P<local_url>(file):\/\/[0-9a-zA-Z\$\-\_\+\!`\(\)\,\.\?\/\;\:\&\=\%\#]*)",
    ]


class NameHighlighter(RegexHighlighter):
    """Apply style to names."""

    base_style = "name."
    highlights = [
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
    highlights = [
        r"(?P<completed_state>Completed)",
        r"(?P<cancelled_state>Cancelled)",
        r"(?P<failed_state>Failed)",
        r"(?P<crashed_state>Crashed)",
    ]


class PrefectConsoleHighlighter(RegexHighlighter):
    """Applies style from multiple highlighters."""

    base_style = "log."
    highlights = (
        LevelHighlighter.highlights
        + UrlHighlighter.highlights
        + NameHighlighter.highlights
        + StateHighlighter.highlights
    )
