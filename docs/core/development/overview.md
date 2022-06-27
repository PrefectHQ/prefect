---
sidebarDepth: 0
title: Overview
---

# Development Overview

Thanks for contributing to Prefect! This section of the docs is designed to help you become familiar with how we work, the standards we apply, and how to ensure your contribution is successful.

If you're stuck, don't be shy about asking for help [on GitHub](https://github.com/PrefectHQ/prefect/issues/new/choose) or in the `#prefect-contributors` channel of our [Slack community](https://www.prefect.io/slack). You can also ask us any question in our [Discourse](https://discourse.prefect.io) forum.


!!! tip Working on Server & UI
    The source code for [Prefect Server](https://github.com/PrefectHQ/server) and [Prefect UI](https://github.com/PrefectHQ/ui) is contained in their respective development repos.
:::

## Getting Started

### Clone prefect

To clone Prefect for development, we recommend creating an "editable" install of Prefect's master branch, including all development dependencies:

```bash
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
pip install -e ".[dev]"
```

### Write your code!

We have no doubt you can write amazing code! However, we want to help you ensure your code plays nicely with the rest of the Prefect ecosystem. Many projects describe code style and documentation as a suggestion; in Prefect it's a unit-tested requirement.

- To learn how to style your code, see the [style guide](style.md).
- To learn how to document your code, see the [docs guide](documentation.md).
- To learn how to test your code, see the [tests guide](tests.md).
- To learn about contributing, see the [contribution guide](contributing.md).

### Submit your code

In order to submit code to Prefect, please:

- [Fork the Prefect repository](https://help.github.com/en/articles/fork-a-repo)
- [Create a new branch](https://help.github.com/en/desktop/contributing-to-projects/creating-a-branch-for-your-work) on your fork
- [Open a Pull Request](https://help.github.com/en/articles/creating-a-pull-request-from-a-fork) once your work is ready for review
- A Core maintainer will review your PR and provide feedback on any changes it requires to be approved. Once approved, your PR will be merged into Prefect.

### Congratulations!

You're a Prefect contributor - welcome to the team! 🎉
