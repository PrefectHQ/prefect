from pathlib import Path
from typing import Any, List, Tuple, Union

from prefect.core import Task
from prefect.utilities.tasks import defaults_from_attrs
from python_http_client.client import Response


class SendEmail(Task):
    """
    A task for sending an email via Twilio SendGrid.

    Args:
        - from_email (str): The email address of the sender; defaults to notifications@prefect.io
        - to_emails (Union[str, Tuple[str, str], List[str], List[Tuple[str, str]]]):
            The email address of the recipient(s); can also be provided at runtime.
            Refer to [SendGrid-Python](https://github.com/sendgrid/sendgrid-python) for specifics.
        - subject (str, optional): The subject of the email; can also be provided at runtime
        - html_content (str): The html body of the email; can also be provided at runtime
        - category (Union[str, List[str]], optional): The category/categories to use for the email;
            can also be provided at runtime
        - attachment_file_path (Union[str, Path], optional): The file path of the email attachment;
            can also be provided at runtime
        - sendgrid_api_key (str): The SendGrid API key used for authentication;
            can also be provided at runtime, which is preferred since a secret can be used
        - **kwargs (optional): additional kwargs to pass to the `Task` constructor
    """

    def __init__(
        self,
        from_email: str = "notifications@prefect.io",
        to_emails: Union[str, Tuple[str, str], List[str], List[Tuple[str, str]]] = None,
        subject: str = None,
        html_content: str = None,
        category: Union[str, List[str]] = None,
        attachment_file_path: Union[str, Path] = None,
        sendgrid_api_key: str = None,
        **kwargs: Any
    ):
        self.from_email = from_email
        self.to_emails = to_emails
        self.subject = subject
        self.html_content = html_content
        self.category = category
        self.attachment_file_path = attachment_file_path
        self.sendgrid_api_key = sendgrid_api_key
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "from_email",
        "to_emails",
        "subject",
        "html_content",
        "category",
        "attachment_file_path",
        "sendgrid_api_key",
    )
    def run(
        self,
        from_email: str = "notifications@prefect.io",
        to_emails: Union[str, Tuple[str, str], List[str], List[Tuple[str, str]]] = None,
        subject: str = None,
        html_content: str = None,
        category: Union[str, List[str]] = None,
        attachment_file_path: Union[str, Path] = None,
        sendgrid_api_key: str = None,
    ) -> Response:
        """
        Run message which sends an email via SendGrid.

        Args:
            - from_email (str): The email address of the sender;
                defaults to the one provided at initialization
            - to_emails (Union[str, Tuple[str, str], List[str], List[Tuple[str, str]]]):
                The email address of the recipient(s); defaults to the one provided at initialization.
                Refer to [SendGrid-Python](https://github.com/sendgrid/sendgrid-python) for specifics.
            - subject (str, optional): The subject of the email;
                defaults to the one provided at initialization
            - html_content (str): The html body of the email;
                defaults to the one provided at initialization
            - category (Union[str, List[str]], optional): The category/categories to use for the email;
                defaults to those provided at initialization
            - attachment_file_path (Union[str, Path], optional): The file path of the email attachment;
                defaults to the one provided at initialization
            - sendgrid_api_key (str, optional): The SendGrid API key used for authentication;
                if not provided here, will use the value provided at initialization

        Raises:
            - ValueError: if no API key is provided

        Returns:
            - python_http_client.client.Response:
                A [Python-HTTP-Client](https://github.com/sendgrid/python-http-client) object
                indicating the status of the response
        """

        # Based on the SendGrid example use-case code here:
        # https://github.com/sendgrid/sendgrid-python/blob/aa39f715a061f0de993811faea0adb8223657d01/use_cases/attachment.md

        if not sendgrid_api_key:
            raise ValueError("A SendGrid API key must be provided.")

        import base64
        import mimetypes
        from sendgrid.helpers.mail import (
            Attachment,
            Category,
            Disposition,
            FileContent,
            FileName,
            FileType,
            Mail,
        )
        from sendgrid import SendGridAPIClient

        message = Mail(
            from_email=from_email,
            to_emails=to_emails,
            subject=subject,
            html_content=html_content or "\n",
        )

        if category:
            if not isinstance(category, list):
                category = [category]
            message.category = [Category(str(c)) for c in category]

        if attachment_file_path:
            with open(attachment_file_path, "rb") as f:
                data = f.read()
                f.close()
            encoded = base64.b64encode(data).decode()

            guessed_type, content_encoding = mimetypes.guess_type(
                attachment_file_path, strict=True
            )

            attachment = Attachment()
            attachment.file_content = FileContent(encoded)
            attachment.file_type = FileType(guessed_type)
            attachment.file_name = FileName(Path(attachment_file_path).name)
            attachment.disposition = Disposition("attachment")
            message.attachment = attachment

        sendgrid_client = SendGridAPIClient(sendgrid_api_key)
        response = sendgrid_client.send(message)

        return response
