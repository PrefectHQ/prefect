"""
Tasks for interacting with monday.com

Note, to authenticate with the Monday API add a Prefect Secret
called '"MONDAY_API_TOKEN"' that stores your Monday API Token.
"""

from prefect.tasks.monday.monday import CreateItem
