import pytest

from prefect._internal.pydantic._flags import HAS_PYDANTIC_V2, USE_PYDANTIC_V2

HAS_PYDANTIC_V1 = not HAS_PYDANTIC_V2

DOES_NOT_IMPORT_FROM_V1 = HAS_PYDANTIC_V1 or (HAS_PYDANTIC_V2 and USE_PYDANTIC_V2)
HAS_PYDANTIC_V2_BUT_STILL_IMPORTS_FROM_V1 = HAS_PYDANTIC_V2 and not USE_PYDANTIC_V2


@pytest.mark.skipif(
    DOES_NOT_IMPORT_FROM_V1,
    reason="These tests are only valid when pydantic v2 is installed but we import from pydantic v1.",
)
def test_v2_installed_and_compatibility_layer_disabled():
    import re

    import pydantic

    from prefect import pydantic as prefect_pydantic
    from prefect.pydantic import _dynamic_imports  # type: ignore

    # Ensure that all attributes in prefect.pydantic are imported from pydantic v2
    for attr_name in prefect_pydantic.__all__:
        # Skip dynamic imports
        if attr_name in _dynamic_imports:
            continue
        else:
            # Ensure that the attribute is present in pydantic.v1
            assert hasattr(pydantic.v1, attr_name)

            # Import the attribute from prefect.pydantic, and ensure that it is from pydantic.v1
            attr = getattr(prefect_pydantic, attr_name)
            assert re.findall(r"^pydantic\.v1", attr.__module__)


@pytest.mark.skipif(
    HAS_PYDANTIC_V2_BUT_STILL_IMPORTS_FROM_V1,
    reason="These tests are only valid when pydantic v1 is installed or pydantic v2 is installed but we don't import from pydantic v1.",
)
def test_v2_installed_and_compatibility_layer_enabled():
    import re

    import pydantic

    from prefect import pydantic as prefect_pydantic
    from prefect.pydantic import _dynamic_imports  # type: ignore

    for attr_name in prefect_pydantic.__all__:
        if attr_name in _dynamic_imports:
            continue
        else:
            assert hasattr(pydantic, attr_name)
            attr = getattr(prefect_pydantic, attr_name)
            assert re.findall(r"^pydantic\.(?!v1)", attr.__module__)
