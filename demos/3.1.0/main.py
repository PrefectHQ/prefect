from prefect import flow, task
from prefect.artifacts import create_table_artifact
import pandas as pd


@task
def load_big_dataset_chunks() -> list[pd.DataFrame]:
    # Create a large dataset (100,000 rows)
    df = pd.DataFrame(
        {"value": range(100_000), "group": [f"group_{i}" for i in range(10)] * 10_000}
    )
    return [group_df for _, group_df in df.groupby("group")]


@task
def process_data_chunk(df: pd.DataFrame) -> dict:
    return {
        "group": df["group"].iloc[0],
        "mean": float(df["value"].mean()),
        "count": len(df),
    }


@task
def save_table_artifact(table: list[dict]):
    create_table_artifact(
        key="data-analysis", table=table, description="Analysis of data chunks"
    )


@flow(name="Data Analysis Flow")
def analyze_dataset():
    df_chunks = load_big_dataset_chunks()

    results = process_data_chunk.map(df_chunks)

    save_table_artifact(results)


if __name__ == "__main__":
    from prefect.settings import Settings

    settings = Settings()
    breakpoint()
    analyze_dataset()
