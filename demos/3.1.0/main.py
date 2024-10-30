# /// script
# dependencies = [
#     "prefect@git+https://github.com/PrefectHQ/prefect.git",
#     "prefect-aws",
#     "pandas",
#     "numpy",
# ]
# ///

# if you have uv installed, you can run this file directly with `uv run demos/3.1.0/main.py`
# read more about inline-script metadata here: https://docs.astral.sh/uv/guides/scripts/#declaring-script-dependencies

from pathlib import Path
from prefect import flow, task
from prefect.artifacts import create_table_artifact
from prefect.runner.storage import GitRepository
from prefect.docker import DockerImage
import pandas as pd

from prefect.cache_policies import INPUTS, TASK_SOURCE

CACHE_POLICY = (INPUTS + TASK_SOURCE).configure(key_storage="big-dataset-cache-keys")


@task(cache_policy=CACHE_POLICY)
def load_big_dataset(total_rows: int, num_groups: int) -> list[pd.DataFrame]:
    df = pd.DataFrame(
        {
            "value": range(total_rows),
            "group": [f"group-{i}" for i in range(num_groups)]
            * (total_rows // num_groups),
        }
    )

    return [group_df for _, group_df in df.groupby("group")]


@task(task_run_name="process-data-in-{df.group.iloc[0]}")
def process_data_chunk(df: pd.DataFrame) -> dict:
    return {
        "group": df["group"].iloc[0],
        "mean": float(df["value"].mean()),
        "count": len(df),
    }


@task
def save_table_artifact(table: list[dict]):
    create_table_artifact(
        key="data-analysis",
        table=sorted(table, key=lambda x: int(x["group"].split("-")[1])),
        description="Analysis of data chunks",
    )


@flow
def analyze_dataset(total_rows: int = 1_000_000, num_groups: int = 50):
    df_chunks = load_big_dataset(total_rows, num_groups)

    results = process_data_chunk.map(df_chunks)

    save_table_artifact(results)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "deploy":
        image = DockerImage(
            name="data-analysis-flow",
            tag="demo",
            dockerfile=str(Path(__file__).parent / "Dockerfile"),
        )
        repo = GitRepository(
            url="https://github.com/PrefectHQ/prefect.git",
            branch="demos",
        )
        analyze_dataset.from_source(
            source=repo,
            entrypoint="demos/3.1.0/main.py:analyze_dataset",
        ).deploy(
            name="data-analysis-demo",
            work_pool_name="docker-work",
            image=image,
            build=True,
            push=False,
        )
    else:
        # Otherwise just run the flow
        analyze_dataset()
