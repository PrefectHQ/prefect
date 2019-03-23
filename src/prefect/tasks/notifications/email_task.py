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
    Task for sending email from an authenticated Gmail address.  For this task to function properly,
    you must have the `"EMAIL_USERNAME"` and `"EMAIL_PASSWORD"` Prefect Secrets set.  It is recommended
    you use a [Google App Password](https://support.google.com/accounts/answer/185833) for this purpose.

    Args:
        - subject (str, optional): the subject of the email; can also be provided at runtime
        - msg (str, optional): the contents of the email; can also be provided at runtime
        - email_to (str, optional): the destination email address to send the message to; can also
            be provided at runtime
        - **kwargs (Any, optional): additional keyword arguments to pass to the base Task initialization
    """

    def __init__(
        self, subject: str = None, msg: str = None, email_to: str = None, **kwargs: Any
    ):
        self.subject = subject
        self.msg = msg
        self.email_to = email_to
        super().__init__(**kwargs)

    @defaults_from_attrs("subject", "msg", "email_to")
    def run(self, subject: str = None, msg: str = None, email_to: str = None) -> None:
        """
        Run method which sends an email.

        Args:
            - subject (str, optional): the subject of the email; defaults to the one provided
                at initialization
            - msg (str, optional): the contents of the email; defaults to the one provided
                at initialization
            - email_to (str, optional): the destination email address to send the message to;
                defaults to the one provided at initialization

        Returns:
            - None
        """

        username = cast(str, Secret("EMAIL_USERNAME").get())
        password = cast(str, Secret("EMAIL_PASSWORD").get())
        email_to = cast(str, email_to)

        contents = MIMEMultipart("alternative")
        contents.attach(MIMEText(cast(str, msg), "plain"))

        contents["Subject"] = Header(subject, "UTF-8")
        contents["From"] = "notifications@prefect.io"
        contents["To"] = email_to

        message = contents.as_string()

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(username, password)
        try:
            server.sendmail("notifications@prefect.io", email_to, message)
        finally:
            server.quit()
