from datetime import datetime

from prefect.server.utilities.user_templates import render_user_template


async def test_user_templates_have_humanize_available():
    rendered = await render_user_template(
        "{{when|humanize_naturalday}}",
        {"when": datetime(2023, 1, 2, 3, 4, 5)},
    )
    assert rendered == "Jan 02"
