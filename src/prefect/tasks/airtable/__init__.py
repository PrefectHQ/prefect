"""
A collection of tasks for interacting with Airtable.
"""
try:
    from prefect.tasks.airtable.airtable import WriteAirtableRow, ReadAirtableRow
except ImportError:
    raise ImportError(
        'Using `prefect.tasks.airtable` requires Prefect to be installed with the "airtable" extra.'
    )
