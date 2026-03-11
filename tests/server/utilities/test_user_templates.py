from datetime import datetime

import pytest

from prefect.server.utilities.user_templates import (
    TemplateRenderError,
    render_user_template,
    render_user_template_sync,
)


async def test_user_templates_have_humanize_available():
    rendered = await render_user_template(
        "{{when|humanize_naturalday}}",
        {"when": datetime(2023, 1, 2, 3, 4, 5)},
    )
    assert rendered == "Jan 02"


async def test_render_user_template_raises_on_error():
    with pytest.raises(TemplateRenderError) as exc_info:
        await render_user_template("{{ foo.bar.baz() }}", {})
    assert exc_info.value.template == "{{ foo.bar.baz() }}"
    assert exc_info.value.error is not None


def test_render_user_template_sync_raises_on_error():
    with pytest.raises(TemplateRenderError) as exc_info:
        render_user_template_sync("{{ foo.bar.baz() }}", {})
    assert exc_info.value.template == "{{ foo.bar.baz() }}"
    assert exc_info.value.error is not None


async def test_render_user_template_no_error_for_plain_strings():
    result = await render_user_template("no templates here", {})
    assert result == "no templates here"


def test_render_user_template_sync_no_error_for_plain_strings():
    result = render_user_template_sync("no templates here", {})
    assert result == "no templates here"
