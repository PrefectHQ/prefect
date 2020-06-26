import ssl
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, cast

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
        - msg (str, optional): the contents of the email; can also be provided at runtime
        - email_to (str, optional): the destination email address to send the message to; can also
            be provided at runtime
        - email_from (str, optional): the email address to send from; defaults to
            notifications@prefect.io
        - smtp_server (str, optional): the hostname of the SMTP server; defaults to smtp.gmail.com
        - smtp_port (int, optional): the port number of the SMTP server; defaults to 465
        - smtp_type (str, optional): either SSL or STARTTLS; defaults to SSL
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
        **kwargs: Any,
    ):
        self.subject = subject
        self.msg = msg
        self.email_to = email_to
        self.email_from = email_from
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_type = smtp_type
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "subject",
        "msg",
        "email_to",
        "email_from",
        "smtp_server",
        "smtp_port",
        "smtp_type",
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

        Returns:
            - None
        """

        username = cast(str, Secret("EMAIL_USERNAME").get())
        password = cast(str, Secret("EMAIL_PASSWORD").get())
        email_to = cast(str, email_to)

        contents = MIMEMultipart("alternative")
        contents.attach(MIMEText(cast(str, msg), "html"))

        contents["Subject"] = Header(subject, "UTF-8")
        contents["From"] = email_from
        contents["To"] = email_to

        message = contents.as_string()
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
            server.sendmail(email_from, email_to, message)
        finally:
            server.quit()
