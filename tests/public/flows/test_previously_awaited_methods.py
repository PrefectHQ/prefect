from prefect import flow, task


async def test_awaiting_formerly_async_methods():
    import warnings

    N = 5

    @task
    def get_random_number(_) -> int:
        return 42

    @flow
    async def get_some_numbers():
        future1 = await get_random_number.submit(None)

        await future1.wait()
        assert await future1.result() == 42

        list_of_futures = await get_random_number.map([None] * N)
        [await future.wait() is None for future in list_of_futures]
        assert all([await future.result() == 42 for future in list_of_futures])

    @flow
    async def get_some_numbers_new_way():
        future1 = get_random_number.submit(None)
        future1.wait()
        assert future1.result() == 42

        list_of_futures = get_random_number.map([None] * N)
        [future.wait() for future in list_of_futures]
        assert all(future.result() == 42 for future in list_of_futures)

    # Test the old way (with await)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        await get_some_numbers()
        assert (
            len(w) == N * 2 + 4
        )  # 1 submit, 1 wait, 1 result, 1 map, N waits, N results
        assert issubclass(w[0].category, DeprecationWarning)
        assert "please remove the `await` keyword" in str(w[0].message)

    # Test the new way (without await)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        await get_some_numbers_new_way()
        assert len(w) == 0
