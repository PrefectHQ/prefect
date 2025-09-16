"""
Compatibility wrapper for starlette status codes.

Starlette 0.48.0 renamed several status codes per RFC 9110.
This module provides backwards-compatible access to these codes.
"""

from starlette import status as _starlette_status


class _StatusCompatibility:
    """
    Compatibility wrapper that maintains old status code names while using new ones where available.

    Maps these renamed codes from RFC 9110:
    - HTTP_422_UNPROCESSABLE_ENTITY -> HTTP_422_UNPROCESSABLE_CONTENT
    - HTTP_413_REQUEST_ENTITY_TOO_LARGE -> HTTP_413_CONTENT_TOO_LARGE
    - HTTP_414_REQUEST_URI_TOO_LONG -> HTTP_414_URI_TOO_LONG
    - HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE -> HTTP_416_RANGE_NOT_SATISFIABLE
    """

    def __getattr__(self, name: str) -> int:
        mapping = {
            "HTTP_422_UNPROCESSABLE_ENTITY": "HTTP_422_UNPROCESSABLE_CONTENT",
            "HTTP_413_REQUEST_ENTITY_TOO_LARGE": "HTTP_413_CONTENT_TOO_LARGE",
            "HTTP_414_REQUEST_URI_TOO_LONG": "HTTP_414_URI_TOO_LONG",
            "HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE": "HTTP_416_RANGE_NOT_SATISFIABLE",
        }

        if name in mapping:
            new_name = mapping[name]
            if hasattr(_starlette_status, new_name):
                return getattr(_starlette_status, new_name)
            elif hasattr(_starlette_status, name):
                return getattr(_starlette_status, name)
            else:
                fallback_values = {
                    "HTTP_422_UNPROCESSABLE_ENTITY": 422,
                    "HTTP_413_REQUEST_ENTITY_TOO_LARGE": 413,
                    "HTTP_414_REQUEST_URI_TOO_LONG": 414,
                    "HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE": 416,
                }
                return fallback_values[name]

        return getattr(_starlette_status, name)


status = _StatusCompatibility()
