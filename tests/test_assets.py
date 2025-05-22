import pytest

from prefect.assets import Asset, ReadOnlyAsset, materialize
from prefect.events.worker import EventsWorker
from prefect.flows import flow
from prefect.tasks import task


def _asset_events(worker: EventsWorker):
    return [e for e in worker._client.events if e.event.startswith("prefect.asset.")]


def _first_event(worker: EventsWorker):
    events = _asset_events(worker)
    assert events, "No asset events were captured by the worker"
    return events[0]


@pytest.mark.parametrize(
    "invalid_key",
    [
        "invalid-key",
        "assets/my-asset",
        "/path/to/file",
        "no-protocol-prefix",
        "UPPERCASE://resource",
        "://missing-protocol",
    ],
)
def test_asset_invalid_uri(invalid_key):
    with pytest.raises(ValueError, match="Key must be a valid URI"):
        Asset(key=invalid_key)


def test_asset_as_resource():
    asset = Asset(
        key="s3://bucket/data",
        name="Test Data",
        metadata={"owner": "data-team", "region": "us-west-2"},
    )

    resource = asset.as_resource()
    assert resource["prefect.resource.id"] == "s3://bucket/data"
    assert resource["prefect.resource.name"] == "Test Data"
    assert resource["owner"] == "data-team"
    assert resource["region"] == "us-west-2"

    asset_no_name = Asset(key="s3://bucket/data", metadata={"owner": "data-team"})
    resource_no_name = asset_no_name.as_resource()
    assert resource_no_name["prefect.resource.id"] == "s3://bucket/data"
    assert "prefect.resource.name" not in resource_no_name
    assert resource_no_name["owner"] == "data-team"


def test_asset_as_related():
    asset = Asset(
        key="postgres://prod/users",
        name="Users",
        metadata={"owner": "data-team"},
    )

    related = asset.as_related()
    assert related["prefect.resource.id"] == "postgres://prod/users"
    assert related["prefect.resource.role"] == "asset"

    assert "owner" not in related
    assert "prefect.resource.name" not in related


def test_asset_read():
    original_asset = Asset(
        key="postgres://prod/users",
        name="Users",
        metadata={"owner": "data-team"},
    )

    read_only = original_asset.read()

    assert isinstance(read_only, ReadOnlyAsset)

    assert read_only.key == original_asset.key
    assert read_only.name == original_asset.name
    assert read_only.metadata == original_asset.metadata

    original_asset.metadata["new_key"] = "value"
    assert "new_key" not in read_only.metadata

    resource = read_only.as_resource()
    assert resource["prefect.resource.id"] == "postgres://prod/users"

    related = read_only.as_related()
    assert related["prefect.resource.id"] == "postgres://prod/users"
    assert related["prefect.resource.role"] == "asset"


def test_single_asset_materialization_success(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    users = Asset(
        key="postgres://prod/users", name="Users", metadata={"region": "us‑east1"}
    )

    @materialize(users)
    def make_users():
        return {"rows": 100}

    @flow
    def pipeline():
        make_users()

    pipeline()
    asserting_events_worker.drain()

    evt = _first_event(asserting_events_worker)
    assert evt.event == "prefect.asset.materialization.succeeded"
    assert evt.resource.id == users.key
    assert evt.resource["prefect.resource.name"] == "Users"
    assert evt.resource["region"] == "us‑east1"
    assert any(r.id.startswith("prefect.flow-run.") for r in evt.related)


def test_single_asset_materialization_failure(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    asset = Asset(key="s3://data/broken", name="Broken")

    @materialize(asset)
    def always_broken():
        raise RuntimeError("boom")

    @flow
    def pipeline():
        try:
            always_broken()
        except RuntimeError:
            pass

    pipeline()
    asserting_events_worker.drain()

    evt = _first_event(asserting_events_worker)
    assert evt.event == "prefect.asset.materialization.failed"
    assert evt.resource.id == asset.key


def test_linear_dependency(asserting_events_worker: EventsWorker, reset_worker_events):
    upstream = Asset(key="postgres://prod/users", name="Raw Users")
    downstream = Asset(key="postgres://prod/users_clean", name="Users Clean")

    @materialize(upstream)
    def extract():
        return {"rows": 10}

    @materialize(downstream)
    def load(data):
        return {"rows": 10}

    @flow
    def pipeline():
        df = extract()
        load(df)

    pipeline()
    asserting_events_worker.drain()

    events = sorted(_asset_events(asserting_events_worker), key=lambda e: e.resource.id)
    assert len(events) == 2

    up_evt, down_evt = events
    assert up_evt.resource.id == upstream.key
    assert down_evt.resource.id == downstream.key
    assert any(r.id == upstream.key and r.role == "asset" for r in down_evt.related)


def test_read_only_observation(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    upstream = Asset(key="postgres://prod/users", name="Users")
    downstream = Asset(key="postgres://prod/users_clean", name="Users Clean")

    @materialize(upstream.read())
    def read_only():
        return {"rows": 1}

    @materialize(downstream)
    def load(data):
        return {"rows": 1}

    @flow
    def pipeline():
        data = read_only()
        load(data)

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    mats = [e for e in events if e.event.startswith("prefect.asset.materialization")]
    obs = [e for e in events if e.event.startswith("prefect.asset.observation")]

    assert len(mats) == 1
    assert len(obs) == 1

    mat_evt = mats[0]
    assert mat_evt.resource.id == downstream.key
    assert any(r.id == upstream.key and r.role == "asset" for r in mat_evt.related)


def test_multiple_assets_single_function(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    user_asset = Asset(key="postgres://prod/users_raw", name="Users Raw")
    orders_asset = Asset(key="postgres://prod/orders_raw", name="Orders Raw")

    @materialize(user_asset, orders_asset)
    def ingest():
        return ({"rows": 1}, {"rows": 1})

    @flow
    def pipeline():
        ingest()

    pipeline()
    asserting_events_worker.drain()

    ids = {e.resource.id for e in _asset_events(asserting_events_worker)}
    assert ids == {user_asset.key, orders_asset.key}


async def test_async_materialization(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    asset = Asset(key="postgres://prod/async", name="Async")

    @materialize(asset)
    async def do_async():
        return {"rows": 5}

    @flow
    async def async_flow():
        await do_async()

    await async_flow()
    await asserting_events_worker.drain()

    evt = _first_event(asserting_events_worker)
    assert evt.event == "prefect.asset.materialization.succeeded"
    assert evt.resource.id == asset.key


def test_fan_in_dependency(asserting_events_worker: EventsWorker, reset_worker_events):
    raw_users = Asset(key="postgres://prod/users", name="Raw Users")
    raw_orders = Asset(key="postgres://prod/orders", name="Raw Orders")
    user_orders = Asset(
        key="postgres://prod/user_orders_enriched", name="Enriched User-Orders"
    )

    @materialize(raw_users)
    def extract_users():
        return {"rows": 10}

    @materialize(raw_orders)
    def extract_orders():
        return {"rows": 20}

    @task
    def enrich(users_df, orders_df):
        return {"rows": 15}

    @materialize(user_orders)
    def load_user_orders(enriched_df):
        return {"rows": 15}

    @flow
    def user_orders_pipeline():
        users_df = extract_users()
        orders_df = extract_orders()
        enriched = enrich(users_df, orders_df)
        load_user_orders(enriched)

    user_orders_pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    assert len(events) == 3

    downstream_events = [e for e in events if e.resource.id == user_orders.key]
    assert len(downstream_events) == 1
    downstream_evt = downstream_events[0]

    assert any(
        r.id == raw_users.key and r.role == "asset" for r in downstream_evt.related
    )
    assert any(
        r.id == raw_orders.key and r.role == "asset" for r in downstream_evt.related
    )

    assert any(r.id.startswith("prefect.flow-run.") for r in downstream_evt.related)


def test_fan_out_dependency(asserting_events_worker: EventsWorker, reset_worker_events):
    events_raw = Asset(key="s3://data/events_raw", name="Raw Events")
    events_daily = Asset(key="s3://data/events_daily", name="Daily Aggregates")
    events_hourly = Asset(key="s3://data/events_hourly", name="Hourly Aggregates")

    @materialize(events_raw)
    def ingest_events():
        return {"rows": 100}

    @task
    def aggregate_daily(df):
        return {"daily_rows": 30}

    @task
    def aggregate_hourly(df):
        return {"hourly_rows": 24}

    @materialize(events_daily)
    def load_daily(df):
        return {"rows": 30}

    @materialize(events_hourly)
    def load_hourly(df):
        return {"rows": 24}

    @flow
    def events_pipeline():
        raw = ingest_events()
        daily_df = aggregate_daily(raw)
        hourly_df = aggregate_hourly(raw)
        load_daily(daily_df)
        load_hourly(hourly_df)

    events_pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    assert len(events) == 3

    daily_events = [e for e in events if e.resource.id == events_daily.key]
    hourly_events = [e for e in events if e.resource.id == events_hourly.key]
    assert len(daily_events) == 1
    assert len(hourly_events) == 1

    for evt in [daily_events[0], hourly_events[0]]:
        assert any(r.id == events_raw.key and r.role == "asset" for r in evt.related)
        # Also check for flow-run context
        assert any(r.id.startswith("prefect.flow-run.") for r in evt.related)


def test_fan_in_to_fan_out_dependency(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    users_raw = Asset(key="postgres://prod/users_raw", name="Users Raw")
    orders_raw = Asset(key="postgres://prod/orders_raw", name="Orders Raw")
    per_user = Asset(key="postgres://prod/orders_per_user", name="Orders Per User")
    summary = Asset(key="postgres://prod/orders_summary", name="Orders Summary")

    @materialize(users_raw, orders_raw)
    def ingest():
        return ({"users": 50}, {"orders": 200})

    @materialize(per_user, summary)
    def build(u_df, o_df):
        return ({"per_user_rows": 50}, {"summary_rows": 10})

    @flow
    def pipeline():
        u_df, o_df = ingest()
        build(u_df, o_df)

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    assert len(events) == 4

    users_events = [e for e in events if e.resource.id == users_raw.key]
    orders_events = [e for e in events if e.resource.id == orders_raw.key]
    per_user_events = [e for e in events if e.resource.id == per_user.key]
    summary_events = [e for e in events if e.resource.id == summary.key]

    assert len(users_events) == 1
    assert len(orders_events) == 1
    assert len(per_user_events) == 1
    assert len(summary_events) == 1

    for evt in [per_user_events[0], summary_events[0]]:
        assert any(r.id == users_raw.key and r.role == "asset" for r in evt.related)
        assert any(r.id == orders_raw.key and r.role == "asset" for r in evt.related)
        # Also check for flow-run context
        assert any(r.id.startswith("prefect.flow-run.") for r in evt.related)


def test_linear_dependency_with_intermediate_task(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    upstream = Asset(key="s3://data/raw_data", name="Raw Data")
    downstream = Asset(key="s3://data/processed_data", name="Processed Data")

    @materialize(upstream)
    def extract():
        return {"rows": 100}

    @task
    def transform(data):
        return {"rows": data["rows"], "processed": True}

    @materialize(downstream)
    def load(transformed_data):
        return {"rows": transformed_data["rows"]}

    @flow
    def pipeline():
        raw_data = extract()
        transformed_data = transform(raw_data)
        load(transformed_data)

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    assert len(events) == 2

    upstream_events = [e for e in events if e.resource.id == upstream.key]
    downstream_events = [e for e in events if e.resource.id == downstream.key]

    assert len(upstream_events) == 1
    assert len(downstream_events) == 1
    downstream_evt = downstream_events[0]
    assert any(
        r.id == upstream.key and r.role == "asset" for r in downstream_evt.related
    )
    assert any(r.id.startswith("prefect.flow-run.") for r in downstream_evt.related)


def test_linear_dependency_with_submit(asserting_events_worker, reset_worker_events):
    upstream = Asset(key="postgres://prod/users_submit", name="Raw Users Submit")
    downstream = Asset(
        key="postgres://prod/users_clean_submit", name="Users Clean Submit"
    )

    @materialize(upstream.read())
    def extract():
        return {"rows": 10}

    @materialize(downstream)
    def load(data):
        return {"rows": 10}

    @flow
    def pipeline():
        fut_up = extract.submit()
        fut_down = load.submit(fut_up)
        # explicitly wait
        fut_down.wait()

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    assert len(events) == 2

    upstream_events = [e for e in events if e.resource.id == upstream.key]
    downstream_events = [e for e in events if e.resource.id == downstream.key]

    assert len(upstream_events) == 1
    assert len(downstream_events) == 1
    downstream_evt = downstream_events[0]
    assert any(
        r.id == upstream.key and r.role == "asset" for r in downstream_evt.related
    )
    assert any(r.id.startswith("prefect.flow-run.") for r in downstream_evt.related)


def test_map_with_asset_dependency(asserting_events_worker, reset_worker_events):
    source_asset = Asset(key="s3://data/source_data", name="Source Data")
    destination_asset = Asset(key="s3://data/processed", name="Processed Data")

    @materialize(source_asset.read())
    def extract_source():
        return ["item1", "item2", "item3"]

    @materialize(destination_asset)
    def process_item(item):
        return {"processed": item}

    @flow
    def pipeline():
        source_data = extract_source()
        process_item.map(source_data)

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)

    assert len(events) == 4

    source_events = [e for e in events if e.resource.id == source_asset.key]
    assert len(source_events) == 1
    assert source_events[0].event == "prefect.asset.observation.succeeded"

    destination_events = [e for e in events if e.resource.id == destination_asset.key]
    assert len(destination_events) == 3

    for evt in destination_events:
        assert evt.event == "prefect.asset.materialization.succeeded"
        assert any(r.id == source_asset.key and r.role == "asset" for r in evt.related)
        assert any(r.id.startswith("prefect.flow-run.") for r in evt.related)


def test_three_stage_materialization_direct_deps_only(
    asserting_events_worker, reset_worker_events
):
    bronze = Asset(key="s3://lake/bronze/users", name="Users Bronze")
    silver = Asset(key="s3://lake/silver/users", name="Users Silver")
    gold = Asset(key="s3://lake/gold/users", name="Users Gold")

    @materialize(bronze)
    def stage_bronze():
        return {"rows": 100}

    @materialize(silver)
    def stage_silver(df):
        return {"rows": df["rows"]}

    @materialize(gold)
    def stage_gold(df):
        return {"rows": df["rows"]}

    @flow
    def pipeline():
        bronze_df = stage_bronze()
        silver_df = stage_silver(bronze_df)
        stage_gold(silver_df)

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    assert len(events) == 3

    def evt_for(asset):
        return next(e for e in events if e.resource.id == asset.key)

    evt_bronze = evt_for(bronze)
    evt_silver = evt_for(silver)
    evt_gold = evt_for(gold)

    assert not any(r.role == "asset" for r in evt_bronze.related)
    assert {r.id for r in evt_silver.related if r.role == "asset"} == {bronze.key}
    assert {r.id for r in evt_gold.related if r.role == "asset"} == {silver.key}

    for e in (evt_bronze, evt_silver, evt_gold):
        assert any(r.id.startswith("prefect.flow-run.") for r in e.related)


def test_snowflake_aggregation_direct_deps_only(
    asserting_events_worker, reset_worker_events
):
    SNOWFLAKE_SCHEMA = "snowflake://my-database/my-schema"

    @materialize(
        Asset(key=f"{SNOWFLAKE_SCHEMA}/table-1-raw", name="Table 1 Raw").read()
    )
    def table_1_raw():
        return "fake data 1"

    @materialize(
        Asset(key=f"{SNOWFLAKE_SCHEMA}/table-2-raw", name="Table 2 Raw").read()
    )
    def table_2_raw():
        return "fake data 2"

    @materialize(
        Asset(key=f"{SNOWFLAKE_SCHEMA}/table-3-raw", name="Table 3 Raw").read()
    )
    def table_3_raw():
        return "fake data 3"

    table_1_cleaned_asset = Asset(
        key=f"{SNOWFLAKE_SCHEMA}/table-1-cleaned", name="Table 1 Cleaned"
    )
    table_2_cleaned_asset = Asset(
        key=f"{SNOWFLAKE_SCHEMA}/table-2-cleaned", name="Table 2 Cleaned"
    )
    table_3_cleaned_asset = Asset(
        key=f"{SNOWFLAKE_SCHEMA}/table-3-cleaned", name="Table 3 Cleaned"
    )

    @materialize(table_1_cleaned_asset)
    def table_1_cleaned(raw_table_1):
        return f"cleaned {raw_table_1}"

    @materialize(table_2_cleaned_asset)
    def table_2_cleaned(raw_table_2):
        return f"cleaned {raw_table_2}"

    @materialize(table_3_cleaned_asset)
    def table_3_cleaned(raw_table_3):
        return f"cleaned {raw_table_3}"

    aggregated_asset = Asset(
        key=f"{SNOWFLAKE_SCHEMA}/aggregated-table", name="Aggregated Table"
    )

    @materialize(aggregated_asset)
    def aggregated_table(cleaned_table_1, cleaned_table_2, cleaned_table_3):
        return None

    @flow
    def my_flow():
        r1 = table_1_raw()
        r2 = table_2_raw()
        r3 = table_3_raw()
        c1 = table_1_cleaned(r1)
        c2 = table_2_cleaned(r2)
        c3 = table_3_cleaned(r3)
        aggregated_table(c1, c2, c3)

    my_flow()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    assert len(events) == 7

    by_id = {e.resource.id: e for e in events}

    for raw_key in (
        f"{SNOWFLAKE_SCHEMA}/table-1-raw",
        f"{SNOWFLAKE_SCHEMA}/table-2-raw",
        f"{SNOWFLAKE_SCHEMA}/table-3-raw",
    ):
        evt = by_id[raw_key]
        assert evt.event == "prefect.asset.observation.succeeded"
        assert not any(r.role == "asset" for r in evt.related)

    for cleaned_key, raw_key in [
        (table_1_cleaned_asset.key, f"{SNOWFLAKE_SCHEMA}/table-1-raw"),
        (table_2_cleaned_asset.key, f"{SNOWFLAKE_SCHEMA}/table-2-raw"),
        (table_3_cleaned_asset.key, f"{SNOWFLAKE_SCHEMA}/table-3-raw"),
    ]:
        evt = by_id[cleaned_key]
        upstream = {r.id for r in evt.related if r.role == "asset"}
        assert upstream == {raw_key}

    agg_evt = by_id[aggregated_asset.key]
    upstream_assets = {r.id for r in agg_evt.related if r.role == "asset"}
    assert upstream_assets == {
        table_1_cleaned_asset.key,
        table_2_cleaned_asset.key,
        table_3_cleaned_asset.key,
    }

    for e in events:
        assert any(r.id.startswith("prefect.flow-run.") for r in e.related)


def test_asset_dependency_with_wait_for(asserting_events_worker, reset_worker_events):
    source_asset = Asset(key="s3://data/dependencies/source", name="Source Data")
    dependent_asset = Asset(
        key="s3://data/dependencies/dependent", name="Dependent Data"
    )

    @materialize(source_asset.read())
    def create_source():
        return {"source_data": "value"}

    @materialize(dependent_asset)
    def create_dependent():
        return {"dependent_data": "processed"}

    @flow
    def pipeline():
        source_future = create_source.submit()
        dependent_future = create_dependent.submit(wait_for=source_future)
        dependent_future.wait()

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    assert len(events) == 2

    source_events = [e for e in events if e.resource.id == source_asset.key]
    dependent_events = [e for e in events if e.resource.id == dependent_asset.key]

    assert len(source_events) == 1
    assert len(dependent_events) == 1

    dependent_evt = dependent_events[0]
    assert any(
        r.id == source_asset.key and r.role == "asset" for r in dependent_evt.related
    )
    assert any(r.id.startswith("prefect.flow-run.") for r in dependent_evt.related)
