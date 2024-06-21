from prefect import flow, task


async def test_awaiting_formerly_async_methods():
    import warnings

    N = 5

    @task
    def get_random_number(_) -> int:
        return 42

    @flow
    async def get_some_numbers_old_await_syntax():
        state1 = await get_random_number.submit(None, return_state=True)
        assert state1.is_completed()

        future1 = await get_random_number.submit(None)

        await future1.wait()
        assert await future1.result() == 42

        list_of_futures = await get_random_number.map([None] * N)
        [await future.wait() for future in list_of_futures]
        assert all([await future.result() == 42 for future in list_of_futures])

    @flow
    async def get_some_numbers_new_way():
        state1 = get_random_number.submit(None, return_state=True)
        assert state1.is_completed()

        future1 = get_random_number.submit(None)
        future1.wait()
        assert future1.result() == 42

        list_of_futures = get_random_number.map([None] * N)
        [future.wait() for future in list_of_futures]
        assert all(future.result() == 42 for future in list_of_futures)

    # Test the old way (with await)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        await get_some_numbers_old_await_syntax()
        deprecation_warnings = [
            _w for _w in w if issubclass(_w.category, DeprecationWarning)
        ]

        assert (
            len(deprecation_warnings) == N * 2 + 5
        )  # 1 return_state, 1 submit, 1 wait, 1 result, 1 map, N waits, N results
        assert all(
            "please remove the `await` keyword" in str(warning.message)
            for warning in deprecation_warnings
        )

    # Test the new way (without await)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        await get_some_numbers_new_way()
        deprecation_warnings = [
            _w for _w in w if issubclass(_w.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) == 0
