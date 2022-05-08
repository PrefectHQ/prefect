"""
Tasks for interacting with any SFTP server.
"""
try:
    from prefect.tasks.sftp.sftp import SftpDownload, SftpDownload
except ImportError as err:
    raise ImportError(
        'prefect.tasks.sftp` requires Prefect to be installed with the "sftp" extra.'
    ) from err
