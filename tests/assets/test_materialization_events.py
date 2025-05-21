from prefect.assets import Asset, materialize
from prefect.events.worker import EventsWorker
from prefect.flows import flow
from prefect.tasks import task


def _asset_events(worker: EventsWorker):
    return [e for e in worker._client.events if e.event.startswith("prefect.asset.")]


def _first_event(worker: EventsWorker):
    events = _asset_events(worker)
    assert events, "No asset events were captured by the worker"
    return events[0]


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
    # Flow‑run context must be present
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
    # two events: upstream then downstream
    assert len(events) == 2

    up_evt, down_evt = events
    assert up_evt.resource.id == upstream.key
    assert down_evt.resource.id == downstream.key

    # Downstream must reference upstream in related‑assets
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
    # Should have exactly **one** materialization (the downstream)
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
    # Should have 3 events (2 upstream assets + 1 downstream)
    assert len(events) == 3

    # Get the downstream event
    downstream_events = [e for e in events if e.resource.id == user_orders.key]
    assert len(downstream_events) == 1
    downstream_evt = downstream_events[0]

    # Check that downstream event references both upstream assets in related resources
    assert any(
        r.id == raw_users.key and r.role == "asset" for r in downstream_evt.related
    )
    assert any(
        r.id == raw_orders.key and r.role == "asset" for r in downstream_evt.related
    )

    # Verify flow-run context is present
    assert any(r.id.startswith("prefect.flow-run.") for r in downstream_evt.related)


def test_fan_out_dependency(asserting_events_worker: EventsWorker, reset_worker_events):
    # Case #5: 1 upstream asset -> 2 downstream assets
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
    # Should have 3 events (1 upstream + 2 downstream)
    assert len(events) == 3

    # Get the downstream events
    daily_events = [e for e in events if e.resource.id == events_daily.key]
    hourly_events = [e for e in events if e.resource.id == events_hourly.key]
    assert len(daily_events) == 1
    assert len(hourly_events) == 1

    # Both downstream events should reference the same upstream asset
    for evt in [daily_events[0], hourly_events[0]]:
        assert any(r.id == events_raw.key and r.role == "asset" for r in evt.related)
        # Also check for flow-run context
        assert any(r.id.startswith("prefect.flow-run.") for r in evt.related)


def test_fan_in_to_fan_out_dependency(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    # Case #6: 2 upstream assets -> 2 downstream assets
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
    # Should have 4 events total (2 upstream + 2 downstream)
    assert len(events) == 4

    # Get events for each asset
    users_events = [e for e in events if e.resource.id == users_raw.key]
    orders_events = [e for e in events if e.resource.id == orders_raw.key]
    per_user_events = [e for e in events if e.resource.id == per_user.key]
    summary_events = [e for e in events if e.resource.id == summary.key]

    # Verify one event per asset
    assert len(users_events) == 1
    assert len(orders_events) == 1
    assert len(per_user_events) == 1
    assert len(summary_events) == 1

    # Each downstream event should reference both upstream assets
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
    # Should have 2 events (1 upstream + 1 downstream)
    assert len(events) == 2

    # Get events for each asset
    upstream_events = [e for e in events if e.resource.id == upstream.key]
    downstream_events = [e for e in events if e.resource.id == downstream.key]

    # Verify one event per asset
    assert len(upstream_events) == 1
    assert len(downstream_events) == 1

    # Downstream event should reference the upstream asset
    downstream_evt = downstream_events[0]
    assert any(
        r.id == upstream.key and r.role == "asset" for r in downstream_evt.related
    )

    # Verify flow-run context is present
    assert any(r.id.startswith("prefect.flow-run.") for r in downstream_evt.related)
