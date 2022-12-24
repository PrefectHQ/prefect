
# Contribute

## Create custom blocks

### Build a block

Building your own custom block is simple!

1. Subclass from `Block`.
2. Add a description alongside an `Attributes` and `Example` section in the docstring.
3. Set a `_logo_url` to point to a relevant image.
4. Create the `pydantic.Field`s of the block with a type annotation, `default` or `default_factory`, and a short description about the field.
6. Define the methods of the block.

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

### Inherit an existing block

We can build blocks on top of blocks too!

For example, if we wanted a `SecretDict` block, it can inherit from the `Secret` block:

```python
from pydantic import Field
from prefect.blocks.core import Block
from prefect.blocks.system import Secret
from prefect.blocks.fields import SecretDict


class SecretDict(Secret):
    """
    A block that represents a secret dictionary. The dictionary values stored
    in this block will be obfuscated when this block is logged or shown in the UI.

    Attributes:
        value: A dictionary with its values that should be kept secret.

    Example:
        ```python
        from prefect.blocks.system import SecretDict
        secret_block = Secret.load("BLOCK_NAME")

        # Access the stored secret
        secret_block.get()
        ```
    """

    _block_type_name = "Secret Dictionary"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/5uUmyGBjRejYuGTWbTxz6E/3003e1829293718b3a5d2e909643a331/image8.png?h=250"

    value: SecretDict = Field(
        default=..., description="A dictionary with its values that should be kept secret."
    )  # ... indicates it's a required field
```
Just be sure to update `_block_type_name` and `_logo_url` as needed.

Then to use this:
```python
my_secret_dict = SecretDict(value={"a key": "to my deepest secrets"})
print(my_secret_dict)
print(my_secret_dict.get())
```

That should output:
```
SecretDict(value=SecretDict('{'a key': '**********'}'))
{'a key': 'to my deepest secrets'}
```

To view in the Prefect Cloud or Prefect Orion server UI, [register the block](https://orion-docs.prefect.io/concepts/blocks/#registering-blocks-for-use-in-the-prefect-ui).

## Contributing Collections

Anyone can create and share a Prefect Collection and we encourage anyone interested in creating a collection to do so!

### Generate a project

To help you get started with your collection, we've created a template that gives the tools you need to create and publish your collection.

Use the [Prefect Collection template](https://github.com/PrefectHQ/prefect-collection-template#quickstart) to get started creating a collection with a bootstrapped project!

### List a project in the Collections Catalog

To list your collection in the Prefect Collections Catalog, submit a PR to the Prefect repository adding a file to the `docs/collections/catalog` directory with details about your collection. Please use `TEMPLATE.yaml` in that folder as a guide.
