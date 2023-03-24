---
description: Contribute blocks and integrations to the Prefect Integrations Catalog.
tags:
  - blocks
  - storage
  - secrets
  - configuration
  - infrastructure
  - integrations
  - contributing
---

# Contribute

We welcome contributors! You can help contribute blocks and integrations by following these steps.

## Contributing Blocks

Building your own custom block is simple!

1. Subclass from `Block`.
1. Add a description alongside an `Attributes` and `Example` section in the docstring.
1. Set a `_logo_url` to point to a relevant image.
1. Create the `pydantic.Field`s of the block with a type annotation, `default` or `default_factory`, and a short description about the field.
1. Define the methods of the block.

For example, this is how the [Secret block is implemented](https://github.com/PrefectHQ/prefect/blob/main/src/prefect/blocks/system.py#L76-L102):
```python
from pydantic import Field, SecretStr
from prefect.blocks.core import Block

class Secret(Block):
    """
    A block that represents a secret value. The value stored in this block will be obfuscated when
    this block is logged or shown in the UI.

    Attributes:
        value: A string value that should be kept secret.

    Example:
        ```python
        from prefect.blocks.system import Secret
        secret_block = Secret.load("BLOCK_NAME")

        # Access the stored secret
        secret_block.get()
        ```
    """

    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/5uUmyGBjRejYuGTWbTxz6E/3003e1829293718b3a5d2e909643a331/image8.png?h=250"

    value: SecretStr = Field(
        default=..., description="A string value that should be kept secret."
    )  # ... indicates it's a required field

    def get(self):
        return self.value.get_secret_value()
```

To view in the Prefect Cloud or Prefect server UI, [register the block](https://docs.prefect.io/concepts/blocks/#registering-blocks-for-use-in-the-prefect-ui).

## Contributing Integrations

Anyone can create and share a Prefect Integration and we encourage anyone interested in creating a integration to do so!

### Generate a project

To help you get started with your integration, we've created a template that gives the tools you need to create and publish your integration.

Use the [Prefect Integration template](https://github.com/PrefectHQ/prefect-integration-template#quickstart) to get started creating an integration with a bootstrapped project!

### List a project in the Integrations Catalog

To list your integration in the Prefect Integrations Catalog, submit a PR to the Prefect repository adding a file to the `docs/integrations/catalog` directory with details about your integration. Please use `TEMPLATE.yaml` in that folder as a guide.

## Contribute fixes or enhancements to Integrations

If you'd like to help contribute to fix an issue or add a feature to any of our Integrations, please [propose changes through a pull request from a fork of the repository](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork).

1. [Fork the repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#forking-a-repository)
2. [Clone the forked repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#cloning-your-forked-repository)
3. Install the repository and its dependencies:
```
pip install -e ".[dev]"
```
4. Make desired changes
5. Add tests
6. Insert an entry to the Integration's CHANGELOG.md
7. Install `pre-commit` to perform quality checks prior to commit:
```
pre-commit install
```
8. `git commit`, `git push`, and create a pull request
