"""
A collection of tasks for interacting with Airtable.
"""
try:
    from prefect.tasks.airtable.airtable import WriteAirtableRow
except ImportError:
    raise ImportError(
        'Using `prefect.tasks.airtable` requires Prefect to be installed with the "airtable" extra.'
    )
