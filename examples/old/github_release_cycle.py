"""
This flow attempts to prompt a biweekly release by opening a PR from dev -> master every other Monday.

If for any reason the PR fails to open, the Flow opens an issue alerting the team, with
relevant debug information.
"""
import datetime

import pendulum

from prefect import Flow, task
from prefect.schedules import IntervalSchedule
from prefect.tasks.github import CreateGitHubPR, OpenGitHubIssue
from prefect.triggers import any_failed

pr_task = CreateGitHubPR(
    name="Open dev->master PR",
    repo="PrefectHQ/cloud",
    base="master",
    head="dev",
    title="Bi-weekly Release",
    max_retries=1,
    retry_delay=datetime.timedelta(minutes=1),
)


@task(trigger=any_failed)
def prepare_exception(exc):
    return repr(exc)


issue_task = OpenGitHubIssue(
    name="Open Release Issue",
    repo="PrefectHQ/cloud",
    title="Release Cycle is Broken",
    labels=["release", "bug"],
)


biweekly_schedule = IntervalSchedule(
    start_date=pendulum.parse("2019-03-18"), interval=datetime.timedelta(days=14)
)


with Flow("Biweekly Cloud Release", schedule=biweekly_schedule) as flow:
    exc = prepare_exception(pr_task)  # will only run if pr_task fails in some way
    issue = issue_task(body=exc)


flow.set_reference_tasks([pr_task])
flow.run()
