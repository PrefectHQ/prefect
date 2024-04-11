"""Utilities to support safely rendering user-supplied templates"""

from typing import Any, Dict, List, Optional, Set

import jinja2.sandbox
from jinja2 import ChainableUndefined, nodes
from jinja2.sandbox import ImmutableSandboxedEnvironment

from prefect.logging import get_logger

logger = get_logger(__name__)


jinja2.sandbox.MAX_RANGE = 100
MAX_LOOP_COUNT = 10
MAX_NESTED_LOOP_DEPTH = 2


_template_environment = ImmutableSandboxedEnvironment(
    undefined=ChainableUndefined,
    enable_async=True,
    extensions=[
        # Supports human-friendly rendering of dates and times
        # https://pypi.org/project/jinja2-humanize-extension/
        "jinja2_humanize_extension.HumanizeExtension",
    ],
)

_sync_template_environment = ImmutableSandboxedEnvironment(
    undefined=ChainableUndefined,
    enable_async=False,
    extensions=[
        # Supports human-friendly rendering of dates and times
        # https://pypi.org/project/jinja2-humanize-extension/
        "jinja2_humanize_extension.HumanizeExtension",
    ],
)


class TemplateSecurityError(Exception):
    """Raised when extended validation of a template fails."""

    def __init__(self, message: Optional[str] = None, line_number: int = 0) -> None:
        self.lineno = line_number
        self.message = message
        super().__init__(message)


def register_user_template_filters(filters: Dict[str, Any]):
    """Register additional filters that will be available to user templates"""
    _template_environment.filters.update(filters)


def validate_user_template(template: str):
    root_node = _template_environment.parse(template)
    _validate_loop_constraints(root_node)


def _validate_loop_constraints(root_node: nodes.Template):
    for_nodes = [node for node in root_node.find_all(nodes.For)]

    if not for_nodes:
        return

    if len(for_nodes) > MAX_LOOP_COUNT:
        raise TemplateSecurityError(
            f"Contains {len(for_nodes)} for loops. Templates can contain no "
            f"more than {MAX_LOOP_COUNT} for loops."
        )

    max_nested_depth = max(_nested_loop_depth(for_node) for for_node in for_nodes)
    if max_nested_depth > MAX_NESTED_LOOP_DEPTH:
        raise TemplateSecurityError(
            f"Contains nested for loops at a depth of {max_nested_depth}. "
            "Templates can nest for loops no more than "
            f"{MAX_NESTED_LOOP_DEPTH} loops deep."
        )


def _nested_loop_depth(node: nodes.Node, depth: int = 0) -> int:
    children = [child for child in node.iter_child_nodes()]

    if isinstance(node, nodes.For):
        depth += 1

    if not children:
        return depth

    return max(_nested_loop_depth(child, depth) for child in children)


def matching_types_in_templates(templates: List[str], types: Set[str]) -> List[str]:
    found = set()

    for template in templates:
        root_node = _template_environment.parse(template)
        for node in root_node.find_all(nodes.Name):
            if node.ctx == "load" and node.name in types:
                found.add(node.name)

    return list(found)


def maybe_template(possible: str) -> bool:
    return "{{" in possible or "{%" in possible


async def render_user_template(template: str, context: Dict[str, Any]) -> str:
    if not maybe_template(template):
        return template

    try:
        loaded = _template_environment.from_string(template)
        return await loaded.render_async(context)
    except Exception as e:
        logger.warning("Unhandled exception rendering template", exc_info=True)
        return (
            f"Failed to render template due to the following error: {e!r}\n"
            "Template source:\n"
        ) + template


def render_user_template_sync(template: str, context: Dict[str, Any]) -> str:
    if not maybe_template(template):
        return template

    try:
        loaded = _sync_template_environment.from_string(template)
        return loaded.render(context)
    except Exception as e:
        logger.warning("Unhandled exception rendering template", exc_info=True)
        return (
            f"Failed to render template due to the following error: {e!r}\n"
            "Template source:\n"
        ) + template
