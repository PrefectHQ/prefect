"""
This ETL-style flow retrieves the number of GitHub "stargazers" and "watchers" for the Prefect repo and writes them to an
Airtable document every day.
"""
import datetime

import pendulum

from prefect import Flow, task
from prefect.schedules import CronSchedule
from prefect.tasks.airtable import WriteAirtableRow
from prefect.tasks.github import GetRepoInfo
from prefect.triggers import any_failed

repo_stats = GetRepoInfo(
    name="Pull star counts",
    repo="PrefectHQ/prefect",
    info_keys=["stargazers_count", "subscribers_count"],
    max_retries=1,
    retry_delay=datetime.timedelta(minutes=1),
)


@task
def process_stats(stats):
    data = {
        "Stars": stats["stargazers_count"],
        "Watchers": stats["subscribers_count"],
        "Date": pendulum.now("utc").isoformat(),
    }
    return data


airtable = WriteAirtableRow(
    base_key="XXXXXXX",
    table_name="Stars",
    max_retries=1,
    retry_delay=datetime.timedelta(minutes=1),
)
daily_schedule = CronSchedule("0 8 * * *")


with Flow("Collect Repo Stats", schedule=daily_schedule) as flow:
    data = process_stats(repo_stats)
    final = airtable(data)


flow.run()
