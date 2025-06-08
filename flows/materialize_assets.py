"""
Demonstrates the use of @materialize to track assets and metadata.
"""

from datetime import datetime
from typing import Any

from prefect import flow, task
from prefect.assets import Asset, materialize

raw_sales_data = Asset(key="s3://data-lake/raw/sales/daily")
cleaned_sales_data = Asset(key="s3://data-lake/cleaned/sales/daily")
sales_summary = Asset(key="s3://data-lake/reports/sales/summary")


@materialize(raw_sales_data)
async def extract_sales_data(date: str) -> dict[str, Any]:
    """Extract raw sales data from source system."""
    print(f"Extracting sales data for {date}")

    data = {
        "date": date,
        "transactions": 1523,
        "total_revenue": 45678.90,
        "regions": ["north", "south", "east", "west"],
    }

    raw_sales_data.add_metadata(
        {
            "extraction_time": datetime.now().isoformat(),
            "record_count": data["transactions"],
            "source_system": "sales_db_prod",
        }
    )

    return data


@materialize(cleaned_sales_data, asset_deps=[raw_sales_data])
async def clean_sales_data(raw_data: dict[str, Any]) -> dict[str, Any]:
    """Clean and validate sales data."""
    print(f"Cleaning sales data for {raw_data['date']}")

    cleaned: dict[str, Any] = {
        "date": raw_data["date"],
        "transactions": raw_data["transactions"],
        "revenue": round(raw_data["total_revenue"], 2),
        "avg_transaction": round(
            raw_data["total_revenue"] / raw_data["transactions"], 2
        ),
        "regions": sorted(raw_data["regions"]),
    }

    cleaned_sales_data.add_metadata(
        {
            "cleaning_time": datetime.now().isoformat(),
            "validation_passed": True,
            "records_cleaned": cleaned["transactions"],
            "quality_score": 0.98,
        }
    )

    return cleaned


@materialize(sales_summary, asset_deps=[cleaned_sales_data])
async def generate_summary(cleaned_data: dict[str, Any]) -> dict[str, Any]:
    """Generate summary report from cleaned data."""
    print(f"Generating summary for {cleaned_data['date']}")

    summary: dict[str, Any] = {
        "report_date": cleaned_data["date"],
        "key_metrics": {
            "total_revenue": cleaned_data["revenue"],
            "transaction_count": cleaned_data["transactions"],
            "avg_transaction_value": cleaned_data["avg_transaction"],
        },
        "regional_coverage": len(cleaned_data["regions"]),
    }

    sales_summary.add_metadata(
        {
            "generation_time": datetime.now().isoformat(),
            "report_type": "daily_summary",
            "format": "json",
        }
    )

    return summary


@task
async def orchestrate_daily_pipeline(date: str) -> dict[str, Any]:
    print(f"Starting daily sales pipeline for {date}")

    try:
        raw_data = await extract_sales_data(date)

        cleaned_data = await clean_sales_data(raw_data)

        summary = await generate_summary(cleaned_data)

        print(f"Pipeline completed successfully for {date}")
        return {"status": "success", "date": date, "summary": summary}

    except Exception as e:
        print(f"Pipeline failed for {date}: {e}")
        return {"status": "failed", "date": date, "error": str(e)}


@task
async def validate_date_range(start_date: str, end_date: str) -> bool:
    """Validate that the date range is reasonable."""
    print(f"Validating date range: {start_date} to {end_date}")
    return True


@flow(name="sales-data-pipeline")
async def sales_pipeline_flow(
    start_date: str = "2024-01-01", end_date: str = "2024-01-01"
):
    print(f"Starting sales pipeline for {start_date} to {end_date}")

    if not await validate_date_range(start_date, end_date):
        print("Invalid date range")
        return

    result = await orchestrate_daily_pipeline(start_date)

    if result["status"] == "success":
        print("Pipeline completed successfully!")
        print(f"Summary: {result['summary']}")
    else:
        print(f"Pipeline failed: {result.get('error')}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(sales_pipeline_flow())
