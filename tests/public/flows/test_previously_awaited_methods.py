from prefect import flow, task


@task
def get_random_number(_) -> int:
    return 42


@flow
async def get_some_numbers():
    future1 = await get_random_number.submit(None)
    assert future1.result() == 42

    list_of_futures = await get_random_number.map([None] * 5)
    assert all(future.result() == 42 for future in list_of_futures)


@flow
async def get_some_numbers_new_way():
    future1 = get_random_number.submit(None)
    assert future1.result() == 42

    list_of_futures = get_random_number.map([None] * 5)
    assert all(future.result() == 42 for future in list_of_futures)


async def test_awaiting_formerly_async_methods():
    import warnings

    # Test the old way (with await)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        await get_some_numbers()
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert "please remove the `await` keyword" in str(w[0].message)

    # Test the new way (without await)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        await get_some_numbers_new_way()
        assert len(w) == 0
