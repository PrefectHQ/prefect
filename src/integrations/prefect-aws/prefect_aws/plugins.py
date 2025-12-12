from __future__ import annotations

import ssl
from typing import Any, Mapping

import boto3
import sqlalchemy as sa

from prefect._experimental.plugins import register_hook
from prefect_aws.settings import AwsSettings


@register_hook
def set_database_connection_params(
    connection_url: str, settings: Any
) -> Mapping[str, Any]:
    iam_settings = AwsSettings().rds.iam

    if not iam_settings.enabled:
        return {}

    url = sa.engine.make_url(connection_url)
    connect_args = {}

    def get_iam_token() -> str:
        session = boto3.Session()
        region = iam_settings.region_name or session.region_name
        client = session.client("rds", region_name=region)
        token = client.generate_db_auth_token(
            DBHostname=url.host,
            Port=url.port or 5432,
            DBUsername=url.username,
            Region=region,
        )
        return token

    # IAM authentication requires SSL
    # Use create_default_context() for secure defaults (cert verification enabled)
    ctx = ssl.create_default_context()
    connect_args["ssl"] = ctx

    connect_args["password"] = get_iam_token

    return connect_args
