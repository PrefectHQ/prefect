import time

from prefect._internal.uuid7 import format_byte_array_as_uuid, uuid7, uuidfromvalues


def test_uuid7():
    """
    Some simple tests
    """
    # Note the sequence value increments by 1 between each of these uuid7(...) calls
    ms = time.time_ns() // 1_000_000
    out1 = str(uuid7(ms))
    out2 = str(uuid7(ms))

    assert out1[:13] == out2[:13]


def test_monotonicity():
    last = ""
    for n in range(100_000):
        i = str(uuid7())
        if n > 0 and i <= last:
            raise RuntimeError(f"UUIDs are not monotonic: {last} versus {i}")


def test_vector():
    # test vectors from
    # https://www.ietf.org/archive/id/draft-peabody-dispatch-new-uuid-format-04.html#name-example-of-a-uuidv7-value

    unix_ts_ms = 0x17F22E279B0
    rand_a = 0xCC3
    rand_b = 0x18C4DC0C0C07398F

    expected = "017f22e279b07cc398c4dc0c0c07398f"
    found = uuidfromvalues(unix_ts_ms, rand_a, rand_b).hex()
    assert expected == found


def test_formatting():
    expected = "017f22e2-79b0-7cc3-98c4-dc0c0c07398f"
    found = format_byte_array_as_uuid(
        b'\x01\x7f"\xe2y\xb0|\xc3\x98\xc4\xdc\x0c\x0c\x079\x8f'
    )
    assert expected == found
