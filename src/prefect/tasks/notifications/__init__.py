"""
Collection of tasks for sending notifications.

Useful for situations in which state handlers are inappropriate.
"""
from prefect.tasks.notifications.gmail_task import GmailTask
from prefect.tasks.notifications.slack_task import SlackTask
