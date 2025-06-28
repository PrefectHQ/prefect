from __future__ import annotations

import os
import time
import uuid
from typing import Callable, Optional


def _time_ms() -> int:
    return time.time_ns() // 1_000_000


def uuid7(
    ms: Optional[int] = None,
    time_func: Callable[[], int] = _time_ms,
) -> uuid.UUID:
    """
    UUID v7, following the proposed extension to RFC4122 described in
    https://www.ietf.org/id/draft-peabody-dispatch-new-uuid-format-02.html.
    All representations (string, byte array, int) sort chronologically,
    with a potential time resolution of 50ns (if the system clock
    supports this).

    Parameters
    ----------

    ms      - Optional integer with the whole number of milliseconds
                since Unix epoch, to set the "as of" timestamp.

    as_type - Optional string to return the UUID in a different format.
                A uuid.UUID (version 7, variant 0x10) is returned unless
                this is one of 'str', 'int', 'hex' or 'bytes'.

    time_func - Set the time function, which must return integer
                milliseconds since the Unix epoch, midnight on 1-Jan-1970.
                Defaults to time.time_ns()/1e6. This is exposed because
                time.time_ns() may have a low resolution on Windows.

    Returns
    -------

    A UUID object, or if as_type is specified, a string, int or
    bytes of length 16.

    Implementation notes
    --------------------

    The 128 bits in the UUID are allocated as follows:
    - 36 bits of whole seconds
    - 24 bits of fractional seconds, giving approx 50ns resolution
    - 14 bits of sequential counter, if called repeatedly in same time tick
    - 48 bits of randomness
    plus, at locations defined by RFC4122, 4 bits for the
    uuid version (0b111) and 2 bits for the uuid variant (0b10).

     0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                           unix_ts_ms                          |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |          unix_ts_ms           |  ver  |       rand_a          |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |var|                        rand_b                             |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                            rand_b                             |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

    Indicative timings:
    - uuid.uuid4()            2.4us
    - uuid7()                 3.7us
    - uuid7(as_type='int')    1.6us
    - uuid7(as_type='str')    2.5us

    Examples
    --------

    ```python
    uuid7()
    # UUID('061cb26a-54b8-7a52-8000-2124e7041024')

    for fmt in ('bytes', 'hex', 'int', 'str', 'uuid', None):
        print(fmt, repr(uuid7(as_type=fmt)))
    # bytes b'\x06\x1c\xb8\xfe\x0f\x0b|9\x80\x00\tjt\x85\xb3\xbb'
    # hex '061cb8fe0f0b7c3980011863b956b758'
    # int 8124504378724980906989670469352026642
    # str '061cb8fe-0f0b-7c39-8003-d44a7ee0bdf6'
    # uuid UUID('061cb8fe-0f0b-7c39-8004-0489578299f6')
    # None UUID('061cb8fe-0f0f-7df2-8000-afd57c2bf446')
    ```
    """
    if ms is None:
        ms = time_func()
    else:
        ms = int(ms)  # Fail fast if not an int

    rand_a = int.from_bytes(bytes=os.urandom(2), byteorder="big")
    rand_b = int.from_bytes(bytes=os.urandom(8), byteorder="big")
    uuid_bytes = uuidfromvalues(ms, rand_a, rand_b)

    uuid_int = int.from_bytes(bytes=uuid_bytes, byteorder="big")
    return uuid.UUID(int=uuid_int)


def uuidfromvalues(unix_ts_ms: int, rand_a: int, rand_b: int):
    version = 0x07
    var = 2
    rand_a &= 0xFFF
    rand_b &= 0x3FFFFFFFFFFFFFFF

    final_bytes = unix_ts_ms.to_bytes(length=6, byteorder="big")
    final_bytes += ((version << 12) + rand_a).to_bytes(length=2, byteorder="big")
    final_bytes += ((var << 62) + rand_b).to_bytes(length=8, byteorder="big")

    return final_bytes


def format_byte_array_as_uuid(arr: bytes):
    return f"{arr[:4].hex()}-{arr[4:6].hex()}-{arr[6:8].hex()}-{arr[8:10].hex()}-{arr[10:].hex()}"


__all__ = ("uuid7",)
