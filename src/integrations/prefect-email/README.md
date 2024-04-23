# prefect-email

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-email/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-email?color=0052FF&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-email/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-email?color=0052FF&labelColor=090422" /></a>
</p>

Visit the full docs [here](https://PrefectHQ.github.io/prefect-email) to see additional examples and the API reference.

`prefect-email` is a collection of prebuilt Prefect integrations that can be used to interact with email services.

## Getting Started

### Integrate with Prefect flows

`prefect-email` makes sending emails effortless, giving you peace of mind that your emails are being sent as expected.

First, install [prefect-email](#installation) and [save your email credentials to a block](#saving-credentials-to-block) to run the examples below!

```python
from prefect import flow
from prefect_email import EmailServerCredentials, email_send_message

@flow
def example_email_send_message_flow(email_addresses):
    email_server_credentials = EmailServerCredentials.load("BLOCK-NAME-PLACEHOLDER")
    for email_address in email_addresses:
        subject = email_send_message.with_options(name=f"email {email_address}").submit(
            email_server_credentials=email_server_credentials,
            subject="Example Flow Notification using Gmail",
            msg="This proves email_send_message works!",
            email_to=email_address,
        )

example_email_send_message_flow(["EMAIL-ADDRESS-PLACEHOLDER"])
```

Outputs:

```bash
16:58:27.646 | INFO    | prefect.engine - Created flow run 'busy-bat' for flow 'example-email-send-message-flow'
16:58:29.225 | INFO    | Flow run 'busy-bat' - Created task run 'email someone@gmail.com-0' for task 'email someone@gmail.com'
16:58:29.229 | INFO    | Flow run 'busy-bat' - Submitted task run 'email someone@gmail.com-0' for execution.
16:58:31.523 | INFO    | Task run 'email someone@gmail.com-0' - Finished in state Completed()
16:58:31.713 | INFO    | Flow run 'busy-bat' - Finished in state Completed('All states completed.')
```

Please note, many email services, like Gmail, require an [App Password](https://support.google.com/accounts/answer/185833) to successfully send emails. If you encounter an error similar to `smtplib.SMTPAuthenticationError: (535, b'5.7.8 Username and Password not accepted...`, it's likely you are not using an App Password.

### Capture exceptions and notify by email

Perhaps you want an email notification with the details of the exception when your flow run fails.

`prefect-email` can be wrapped in an `except` statement to do just that!

```python
from prefect import flow
from prefect.context import get_run_context
from prefect_email import EmailServerCredentials, email_send_message

def notify_exc_by_email(exc):
    context = get_run_context()
    flow_run_name = context.flow_run.name
    email_server_credentials = EmailServerCredentials.load("email-server-credentials")
    email_send_message(
        email_server_credentials=email_server_credentials,
        subject=f"Flow run {flow_run_name!r} failed",
        msg=f"Flow run {flow_run_name!r} failed due to {exc}.",
        email_to=email_server_credentials.username,
    )

@flow
def example_flow():
    try:
        1 / 0
    except Exception as exc:
        notify_exc_by_email(exc)
        raise

example_flow()
```

## Resources

For more tips on how to use tasks and flows in a Collection, check out [Using Collections](https://docs.prefect.io/collections/usage/)!

### Installation

Install `prefect-email` with `pip`:

```bash
pip install prefect-email
```

Then, register to [view the block](https://docs.prefect.io/ui/blocks/) on Prefect Cloud:

```bash
prefect block register -m prefect_email
```

Note, to use the `load` method on Blocks, you must already have a block document [saved through code](https://docs.prefect.io/concepts/blocks/#saving-blocks) or [saved through the UI](https://docs.prefect.io/ui/blocks/).

Requires an installation of Python 3.8+.

We recommend using a Python virtual environment manager such as pipenv, conda or virtualenv.

These tasks are designed to work with Prefect 2. For more information about how to use Prefect, please refer to the [Prefect documentation](https://docs.prefect.io/).

### Saving credentials to block

Note, to use the `load` method on Blocks, you must already have a block document [saved through code](https://docs.prefect.io/concepts/blocks/#saving-blocks) or [saved through the UI](https://docs.prefect.io/ui/blocks/).

Below is a walkthrough on saving block documents through code.

Create a short script, replacing the placeholders.

```python
from prefect_email import EmailServerCredentials

credentials = EmailServerCredentials(
    username="EMAIL-ADDRESS-PLACEHOLDER",
    password="PASSWORD-PLACEHOLDER",  # must be an app password
)
credentials.save("BLOCK-NAME-PLACEHOLDER")
```

Congrats! You can now easily load the saved block, which holds your credentials:

```python
from prefect_email import EmailServerCredentials

EmailServerCredentials.load("BLOCK_NAME_PLACEHOLDER")
```

!!! info "Registering blocks"

    Register blocks in this module to
    [view and edit them](https://docs.prefect.io/ui/blocks/)
    on Prefect Cloud:

    ```bash
    prefect block register -m prefect_email
    ```
