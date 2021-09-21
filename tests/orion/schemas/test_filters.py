from prefect.orion import schemas


def test_filters_without_params_do_not_error():
    class MyFilter(schemas.filters.PrefectFilterBaseModel):
        def _get_filter_list(self):
            return []

    # should not error
    MyFilter().as_sql_filter()
