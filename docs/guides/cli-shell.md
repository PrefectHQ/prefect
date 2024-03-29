---
description: Discover how to use the Prefect CLI for executing shell commands as flows.
tags:
    - CLI
    - Shell Commands
    - Prefect Flows
    - Automation
    - Scheduling
search:
  boost: 2
---

# Orchestrating Shell Commands with Prefect
Harness the power of the Prefect CLI to execute and schedule shell commands as Prefect flows. This guide focuses on using the `watch` and `serve` commands to showcase the CLI's versatility for automation tasks.

Here's what you'll learn:

- Running a shell command as a Prefect flow on-demand with `watch`.
- Scheduling a shell command as a recurring Prefect flow using `serve`.
- The benefits of embedding these commands into your automation workflows.

## Prerequisites
Before you begin, ensure you have:

- An introductory understanding of Prefect and flow concepts. Start with the [Getting Started](/getting-started/quickstart/) guide if you're new.
- Prefect CLI installed, following the instructions in the [Prefect documentation](/getting-started/installation/).
- A command-line environment ready for executing commands.

## The `watch` Command
The `watch` command wraps any shell command in a Prefect flow for instant execution, ideal for quick tasks or integrating shell scripts into your workflows.

### Example Usage
Imagine you want to fetch the current weather in Chicago using the `curl` command. The following Prefect CLI command does just that:

```bash
prefect shell watch "curl http://wttr.in/Chicago?format=3"
```

This command makes a simple request to `wttr.in`, a console-oriented weather service, and prints the weather conditions for Chicago.

### Benefits
- **Immediate Feedback:** Execute shell commands instantly within the Prefect framework for immediate results.
- **Easy Integration:** Seamlessly blend external scripts or data fetching into your data workflows.
- **Visibility and Logging:** Leverage Prefect's logging to track the execution and output of your shell tasks.

## Deploying with `serve`
When you need to run shell commands on a schedule, the `serve` command creates a Prefect deployment for regular execution, streamlining task automation.

### Example Usage
To set up a daily weather report for Chicago at 9 AM, you can use the `serve` command as follows:

```bash
prefect shell serve "curl http://wttr.in/Chicago?format=3" --flow-name "Daily Chicago Weather Report" --cron-schedule "0 9 * * *" --deployment-name "Chicago Weather"
```

This command schedules a Prefect flow to fetch Chicago's weather conditions daily, providing consistent updates without manual intervention.

### Benefits
- **Automated Scheduling:** Schedule shell commands to run automatically, ensuring critical updates are generated and available on time.
- **Centralized Workflow Management:** Manage and monitor your scheduled shell commands alongside Prefect flows for a unified workflow overview.
- **Configurable Execution:** Tailor execution frequency, concurrency limits, and other parameters to suit your project's needs and resources.

## Next Steps
With the `watch` and `serve` commands at your disposal, you're ready to incorporate shell command automation into your Prefect workflows. Start with straightforward tasks like observing cron jobs and expand to more complex automation scenarios to enhance your workflows' efficiency and capabilities.

For more insights into Prefect's features and best practices, visit the [Prefect documentation](https://docs.prefect.io/).