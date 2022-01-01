"""
Collection of tasks for sending notifications.

Useful for situations in which state handlers are inappropriate.
"""
from prefect.tasks.notifications.email_task import EmailTask
from prefect.tasks.notifications.slack_task import SlackTask
from prefect.tasks.notifications.pushbullet_task import PushbulletTask

__all__ = ["EmailTask", "PushbulletTask", "SlackTask"]
