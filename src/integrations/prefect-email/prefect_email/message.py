"""
Tasks for interacting with email message services
"""
# Do NOT rename this module to `email.py` as it
# will conflict with the standard library!

import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import partial
from typing import TYPE_CHECKING, List, Optional, Union

from anyio import to_thread

from prefect import task

if TYPE_CHECKING:
    from prefect_email import EmailServerCredentials


@task
async def email_send_message(
    subject: str,
    msg: str,
    email_server_credentials: "EmailServerCredentials",
    msg_plain: Optional[str] = None,
    email_from: Optional[str] = None,
    email_to: Optional[Union[str, List[str]]] = None,
    email_to_cc: Optional[Union[str, List[str]]] = None,
    email_to_bcc: Optional[Union[str, List[str]]] = None,
    attachments: Optional[List[str]] = None,
):
    """
    Sends an email message from an authenticated email service over SMTP.
    Sending messages containing HTML code is supported - the default MIME
    type is set to the text/html.

    Args:
        subject: The subject line of the email.
        msg: The contents of the email, added as html; can be used in
            combination with msg_plain.
        msg_plain: The contents of the email as plain text,
            can be used in combination with msg.
        email_to: The email addresses to send the message to, separated by commas.
            If a list is provided, will join the items, separated by commas.
        email_to_cc: Additional email addresses to send the message to as cc,
            separated by commas. If a list is provided, will join the items,
            separated by commas.
        email_to_bcc: Additional email addresses to send the message to as bcc,
            separated by commas. If a list is provided, will join the items,
            separated by commas.
        attachments: Names of files that should be sent as attachment.

    Returns:
        MimeText: The MIME Multipart message of the email.

    Example:
        Sends a notification email to someone@gmail.com.
        ```python
        from prefect import flow
        from prefect_email import EmailServerCredentials, email_send_message

        @flow
        def example_email_send_message_flow():
            email_server_credentials = EmailServerCredentials(
                username="username@email.com",
                password="password",
            )
            subject = email_send_message(
                email_server_credentials=email_server_credentials,
                subject="Example Flow Notification",
                msg="This proves email_send_message works!",
                email_to="someone@email.com",
            )
            return subject

        example_email_send_message_flow()
        ```
    """
    message = MIMEMultipart()
    message["Subject"] = subject
    message["From"] = email_from or email_server_credentials.username

    email_to_dict = {"To": email_to, "Cc": email_to_cc, "Bcc": email_to_bcc}
    if all(val is None for val in email_to_dict.values()):
        raise ValueError(
            "One of email_to, email_to_cc, or email_to_bcc must be specified"
        )

    for key, val in email_to_dict.items():
        if isinstance(val, list):
            val = ", ".join(val)
        message[key] = val

    # First add the message in plain text, then the HTML version;
    # email clients try to render the last part first
    if msg_plain:
        message.attach(MIMEText(msg_plain, "plain"))
    if msg:
        message.attach(MIMEText(msg, "html"))

    for filepath in attachments or []:
        with open(filepath, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())

        encoders.encode_base64(part)
        filename = os.path.basename(filepath)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {filename}",
        )
        message.attach(part)

    with email_server_credentials.get_server() as server:
        partial_send_message = partial(server.send_message, message)
        await to_thread.run_sync(partial_send_message)

    return message
