# Email

## EmailTask <Badge text="task"/>

Task for sending email from an authenticated email service over SMTP. For this task to function properly, you must have the `"EMAIL_USERNAME"` and `"EMAIL_PASSWORD"` Prefect Secrets set.  It is recommended you use a [Google App Password](https://support.google.com/accounts/answer/185833) if you use Gmail. The default SMTP server is set to the Gmail SMTP server on port 465 (SMTP-over-SSL)

[API Reference](/api/latest/tasks/notifications.html#emailtask)
