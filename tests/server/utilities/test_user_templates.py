import json
from datetime import datetime

import pytest
from pydantic import BaseModel

from prefect.server.utilities.user_templates import (
    TemplateRenderError,
    register_user_template_filters,
    render_user_template,
    render_user_template_sync,
)


class NestedTemplateModel(BaseModel):
    when: datetime


class TemplateModel(BaseModel):
    name: str
    nested: NestedTemplateModel


async def test_user_templates_have_humanize_available():
    rendered = await render_user_template(
        "{{when|humanize_naturalday}}",
        {"when": datetime(2023, 1, 2, 3, 4, 5)},
    )
    assert rendered == "Jan 02"


async def test_tojson_serializes_pydantic_models():
    rendered = await render_user_template(
        "{{ model | tojson }}",
        {
            "model": TemplateModel(
                name="woodchonk",
                nested=NestedTemplateModel(when=datetime(2023, 1, 2, 3, 4, 5)),
            )
        },
    )

    assert json.loads(rendered) == {
        "name": "woodchonk",
        "nested": {"when": "2023-01-02T03:04:05"},
    }


async def test_render_user_template_raises_on_error():
    with pytest.raises(TemplateRenderError) as exc_info:
        await render_user_template("{{ foo.bar.baz() }}", {})
    assert exc_info.value.template == "{{ foo.bar.baz() }}"
    assert exc_info.value.error is not None


def test_render_user_template_sync_tojson_serializes_nested_pydantic_models():
    rendered = render_user_template_sync(
        "{{ payload | tojson }}",
        {
            "payload": {
                "model": TemplateModel(
                    name="<woodchonk>",
                    nested=NestedTemplateModel(when=datetime(2023, 1, 2, 3, 4, 5)),
                )
            }
        },
    )

    assert "<" not in rendered
    assert json.loads(rendered) == {
        "model": {
            "name": "<woodchonk>",
            "nested": {"when": "2023-01-02T03:04:05"},
        }
    }


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


async def test_registered_filters_are_available_to_sync_and_async_rendering():
    def surround(value: str) -> str:
        return f"({value})"

    register_user_template_filters({"oss_7700_surround": surround})

    assert await render_user_template("{{ 'x' | oss_7700_surround }}", {}) == "(x)"
    assert render_user_template_sync("{{ 'x' | oss_7700_surround }}", {}) == "(x)"
