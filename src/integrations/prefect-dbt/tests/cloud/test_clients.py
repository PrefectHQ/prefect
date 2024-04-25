import json
from unittest.mock import MagicMock

from prefect_dbt.cloud.clients import DbtCloudMetadataClient

import prefect


def test_metadata_client_query(monkeypatch):
    mock_response = {
        "data": {
            "metrics": [
                {
                    "uniqueId": "metric.tpch.total_revenue",
                    "name": "total_revenue",
                    "packageName": "tpch",
                    "tags": [],
                    "label": "Total Revenue ($)",
                    "runId": 108952046,
                    "description": "",
                    "type": "sum",
                    "sql": "net_item_sales_amount",
                    "timestamp": "order_date",
                    "timeGrains": ["day", "week", "month"],
                    "dimensions": ["status_code", "priority_code"],
                    "meta": {},
                    "resourceType": "metric",
                    "filters": [],
                    "model": {"name": "fct_orders"},
                }
            ]
        }
    }
    urlopen_mock = MagicMock()
    urlopen_mock.getcode.return_value = 200
    urlopen_mock.return_value = urlopen_mock
    urlopen_mock.read.return_value = json.dumps(mock_response).encode()
    urlopen_mock.__enter__.return_value = urlopen_mock
    monkeypatch.setattr("urllib.request.urlopen", urlopen_mock)
    dbt_cloud_metadata_client = DbtCloudMetadataClient(api_key="my_api_key")
    mock_query = """
    {
        metrics(jobId: 123) {
            uniqueId
            name
            packageName
            tags
            label
            runId
            description
            type
            sql
            timestamp
            timeGrains
            dimensions
            meta
            resourceType
            filters {
                field
                operator
                value
            }
            model {
                name
            }
        }
    }
    """
    assert dbt_cloud_metadata_client.query(mock_query) == mock_response
    mock_headers = urlopen_mock.call_args_list[0][0][0].headers
    assert mock_headers["X-dbt-partner-source"] == "prefect"
    assert mock_headers["Authorization"] == "Bearer my_api_key"
    assert mock_headers["User-agent"] == f"prefect-{prefect.__version__}"
