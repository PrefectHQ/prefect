import base64
import pathlib

import pytest
from prefect_email.message import email_send_message

from prefect import flow

EMAIL_TO = [
    "someone@email.com",
    "someone@email.com, someone_else@email.com",
    ["some_1@email.com", "some_2@email.com"],
    None,
]
EMAIL_TO_CC = [
    "cc_someone@email.com",
    "cc_someone@email.com, cc_someone_else@email.com",
    ["cc_some_1@email.com", "cc_some_2@email.com"],
    None,
]
EMAIL_TO_BCC = [
    "bcc_someone@email.com",
    "bcc_someone@email.com, bcc_someone_else@email.com",
    ["bcc_some_1@email.com", "bcc_some_2@email.com"],
    None,
]


@pytest.mark.parametrize("email_to", EMAIL_TO)
@pytest.mark.parametrize("email_to_cc", EMAIL_TO_CC)
@pytest.mark.parametrize("email_to_bcc", EMAIL_TO_BCC)
async def test_email_send_message(
    email_to, email_to_cc, email_to_bcc, email_server_credentials
):
    subject = "Example Flow Notification"
    msg_plain = "This proves msg plain is attached first!"
    msg = "<h1>This proves msg is attached second!</h1>"

    attachment = pathlib.Path(__file__).parent.absolute() / "attachment.txt"
    with open(attachment, "rb") as f:
        attachment_text = f.read()

    @flow
    async def test_flow():
        message = await email_send_message(
            email_server_credentials=email_server_credentials,
            subject=subject,
            msg=msg,
            msg_plain=msg_plain,
            attachments=[attachment],
            email_to=email_to,
            email_to_cc=email_to_cc,
            email_to_bcc=email_to_bcc,
        )
        return message

    email_to_dict = {"To": email_to, "Cc": email_to_cc, "Bcc": email_to_bcc}

    if all(val is None for val in email_to_dict.values()):
        with pytest.raises(ValueError):
            await test_flow()
        return

    message = await test_flow()
    assert message["Subject"] == subject
    assert message["From"] == email_server_credentials.username
    assert message.get_payload()[0].get_payload() == msg_plain
    assert message.get_payload()[1].get_payload() == msg
    attachment = message.get_payload()[2].get_payload()
    assert base64.b64decode(attachment) == attachment_text

    for key, val in email_to_dict.items():
        if isinstance(val, list):
            val = ", ".join(val)
        assert message[key] == val
