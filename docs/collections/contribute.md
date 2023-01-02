
# Contribute

We welcome contributors! You can help contribute blocks and collections by following these steps.

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

To view in the Prefect Cloud or Prefect Orion server UI, [register the block](https://orion-docs.prefect.io/concepts/blocks/#registering-blocks-for-use-in-the-prefect-ui).

## Contributing Collections

Anyone can create and share a Prefect Collection and we encourage anyone interested in creating a collection to do so!

### Generate a project

To help you get started with your collection, we've created a template that gives the tools you need to create and publish your collection.

Use the [Prefect Collection template](https://github.com/PrefectHQ/prefect-collection-template#quickstart) to get started creating a collection with a bootstrapped project!

### List a project in the Collections Catalog

To list your collection in the Prefect Collections Catalog, submit a PR to the Prefect repository adding a file to the `docs/collections/catalog` directory with details about your collection. Please use `TEMPLATE.yaml` in that folder as a guide.
