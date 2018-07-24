import smtplib

import prefect

EMAIL_TEMPLATE = """
    From: {email_from}
    To: {email_to}
    Subject: {subject}

    {msg}
    """


class EmailTask(prefect.Task):
    """
    This task sends an email.
    """

    def __init__(self, username=None, password=None, **kwargs):

        self.username = username
        self.password = password

        super().__init__(**kwargs)

    def run(self, subject=None, msg=None, email_from=None, email_to=None):

        message = EMAIL_TEMPLATE.format(
            email_from=email_from, email_to=email_to, subject=subject, msg=msg
        )

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.ehlo()
        server.login(self.username, self.password)
        server.sendmail(from_addr=email_from, to_addrs=email_to, msg=message)
