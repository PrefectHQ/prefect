---
sidebarDepth: 0
title: Overview
---


# Development Overview

To install Prefect for development, we recommend creating an "editable" install of Prefect's master branch, including all development dependencies:

```bash
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
pip install -e ".[dev]"
```

We also recommend developing under Python 3.6+ because Prefect's [style checks](style.md) can only be run on more recent versions of Python, but please note that Prefect maintains compatibility with Python 3.5.2+.

In order to submit code changes to Prefect, please:
- [Fork the Prefect repository](https://help.github.com/en/articles/fork-a-repo)
- [Create a new branch on your Fork](https://help.github.com/en/desktop/contributing-to-projects/creating-a-branch-for-your-work)
- Once your work is complete and ready for review, [open a Pull Request](https://help.github.com/en/articles/creating-a-pull-request-from-a-fork)

## Considerations

We know you can write amazing code! This section of the docs will help make sure that code plays nicely with the rest of the Prefect project. Many projects describe code style and documentation as a suggestion; Prefect makes it a unit-tested requirement.

- To learn how to style your code, see the [style guide](style.md).
- To learn how to document your code, see the [docs guide](documentation.md).
- To learn how to test your code, see the [tests guide](tests.md).
- To learn about contributing, see the [contribution guide](contributing.md).
