"""
This simple flow attempts to prompt a biweekly release by opening a PR from dev -> master every Monday.

If for any reason the PR fails to open, the Flow attempts to open an issue alerting the team, with
relevant debug information.
"""
import datetime
import pendulum

from prefect import Flow, task
from prefect.triggers import any_failed
from prefect.schedules import IntervalSchedule
from prefect.tasks.github import CreateGitHubPR, OpenGitHubIssue


pr_task = CreateGitHubPR(
    name="Open dev->master PR",
    repo="PrefectHQ/cloud",
    base="master",
    head="dev",
    body="Bi-weekly Release",
    max_retries=1,
    retry_delay=datetime.timedelta(minutes=1),
)


prepare_exception = task(repr, name="prepare_exception", trigger=any_failed)


issue_task = OpenGitHubIssue(
    name="Open Release Issue",
    repo="PrefectHQ/prefect",
    title="Release Cycle is Broken",
    labels=["release", "bug"],
)


biweekly_schedule = IntervalSchedule(
    start_date=pendulum.parse("2019-03-18"), interval=datetime.timedelta(days=7)
)


with Flow("Biweekly Cloud Release", schedule=biweekly_schedule) as flow:
    exc = prepare_exception(pr_task)  # will only run if pr_task fails in some way
    issue = issue_task(body=exc)


flow.run()
