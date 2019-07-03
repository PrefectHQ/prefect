"""
Tasks that interface with Dropbox.

Tasks in this collection require a Prefect Secret called `"DROPBOX_ACCESS_TOKEN"` that contains
a valid Dropbox access token.
"""
try:
    from prefect.tasks.dropbox.dropbox import DropboxDownload
except ImportError:
    raise ImportError(
        'Using `prefect.tasks.dropbox` requires Prefect to be installed with the "dropbox" extra.'
    )
