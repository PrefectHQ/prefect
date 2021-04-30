import os
import ssl
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, cast, List

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class EmailTask(Task):
    """
    Task for sending email from an authenticated email service over SMTP. For this task to
    function properly, you must have the `"EMAIL_USERNAME"` and `"EMAIL_PASSWORD"` Prefect
    Secrets set.  It is recommended you use a [Google App
    Password](https://support.google.com/accounts/answer/185833) if you use Gmail.  The default
    SMTP server is set to the Gmail SMTP server on port 465 (SMTP-over-SSL). Sending messages
    containing HTML code is supported - the default MIME type is set to the text/html.

    Args:
        - subject (str, optional): the subject of the email; can also be provided at runtime
        - msg (str, optional): the contents of the email, added as html; can be used in
            combination of msg_plain; can also be provided at runtime
        - email_to (str, optional): the destination email address to send the message to; can also
            be provided at runtime
        - email_from (str, optional): the email address to send from; defaults to
            notifications@prefect.io
        - smtp_server (str, optional): the hostname of the SMTP server; defaults to smtp.gmail.com
        - smtp_port (int, optional): the port number of the SMTP server; defaults to 465
        - smtp_type (str, optional): either SSL or STARTTLS; defaults to SSL
        - msg_plain (str, optional): the contents of the email, added as plain text can be used in
            combination of msg; can also be provided at runtime
        - email_to_cc (str, optional): additional email address to send the message to as cc;
            can also be provided at runtime
        - email_to_bcc (str, optional): additional email address to send the message to as bcc;
            can also be provided at runtime
        - attachments (List[str], optional): names of files that should be sent as attachment; can
            also be provided at runtime
        - **kwargs (Any, optional): additional keyword arguments to pass to the base Task
            initialization
    """

    def __init__(
        self,
        subject: str = None,
        msg: str = None,
        email_to: str = None,
        email_from: str = "notifications@prefect.io",
        smtp_server: str = "smtp.gmail.com",
        smtp_port: int = 465,
        smtp_type: str = "SSL",
        msg_plain: str = None,
        email_to_cc: str = None,
        email_to_bcc: str = None,
        attachments: List[str] = None,
        **kwargs: Any,
    ):
        self.subject = subject
        self.msg = msg
        self.email_to = email_to
        self.email_from = email_from
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_type = smtp_type
        self.msg_plain = msg_plain
        self.email_to_cc = email_to_cc
        self.email_to_bcc = email_to_bcc
        self.attachments = attachments or []
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "subject",
        "msg",
        "email_to",
        "email_from",
        "smtp_server",
        "smtp_port",
        "smtp_type",
        "msg_plain",
        "email_to_cc",
        "email_to_bcc",
        "attachments",
    )
    def run(
        self,
        subject: str = None,
        msg: str = None,
        email_to: str = None,
        email_from: str = None,
        smtp_server: str = None,
        smtp_port: int = None,
        smtp_type: str = None,
        msg_plain: str = None,
        email_to_cc: str = None,
        email_to_bcc: str = None,
        attachments: List[str] = None,
    ) -> None:
        """
        Run method which sends an email.

        Args:
            - subject (str, optional): the subject of the email; defaults to the one provided
                at initialization
            - msg (str, optional): the contents of the email; defaults to the one provided
                at initialization
            - email_to (str, optional): the destination email address to send the message to;
                defaults to the one provided at initialization
            - email_from (str, optional): the email address to send from; defaults to the one
                provided at initialization
            - smtp_server (str, optional): the hostname of the SMTP server; defaults to the one
                provided at initialization
            - smtp_port (int, optional): the port number of the SMTP server; defaults to the one
                provided at initialization
            - smtp_type (str, optional): either SSL or STARTTLS; defaults to the one provided
                at initialization
            - msg_plain (str, optional): the contents of the email, added as plain text can be used in
                combination of msg; defaults to the one provided at initialization
            - email_to_cc (str, optional): additional email address to send the message to as cc;
                defaults to the one provided at initialization
            - email_to_bcc (str, optional): additional email address to send the message to as bcc;
                defaults to the one provided at initialization
            - attachments (List[str], optional): names of files that should be sent as attachment;
                defaults to the one provided at initialization

        Returns:
            - None
        """

        username = cast(str, Secret("EMAIL_USERNAME").get())
        password = cast(str, Secret("EMAIL_PASSWORD").get())

        message = MIMEMultipart()
        message["Subject"] = subject
        message["From"] = email_from
        message["To"] = email_to
        if email_to_cc:
            message["Cc"] = email_to_cc
        if email_to_bcc:
            message["Bcc"] = email_to_bcc

        # First add the message in plain text, then the HTML version. Email clients try to render
        # the last part first
        if msg_plain:
            message.attach(MIMEText(msg_plain, "plain"))
        if msg:
            message.attach(MIMEText(msg, "html"))

        for filepath in attachments:
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

        context = ssl.create_default_context()
        if smtp_type == "SSL":
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context)
        elif smtp_type == "STARTTLS":
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls(context=context)
        else:
            raise ValueError(f"{smtp_type} is an unsupported value for smtp_type.")

        server.login(username, password)
        try:
            server.send_message(message)
        finally:
            server.quit()
