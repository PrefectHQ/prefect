from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi.encoders import jsonable_encoder as fastapi_jsonable_encoder

    jsonable_encoder = fastapi_jsonable_encoder

else:

    def jsonable_encoder(*args: Any, **kwargs: Any) -> Any:
        from fastapi.encoders import jsonable_encoder as fastapi_jsonable_encoder

        return fastapi_jsonable_encoder(*args, **kwargs)
