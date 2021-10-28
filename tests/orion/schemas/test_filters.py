from prefect.orion import schemas


async def test_filters_without_params_do_not_error():
    class MyFilter(schemas.filters.PrefectFilterBaseModel):
        async def _get_filter_list(self):
            return []

    # should not error
    await MyFilter().as_sql_filter()
