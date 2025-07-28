import pytest

from prefect.assets import Asset, AssetProperties, materialize
from prefect.assets.core import MAX_ASSET_DESCRIPTION_LENGTH
from prefect.context import AssetContext
from prefect.events.worker import EventsWorker
from prefect.flows import flow
from prefect.tasks import task
from prefect.types.names import MAX_ASSET_KEY_LENGTH


def _asset_events(worker: EventsWorker):
    return [e for e in worker._client.events if e.event.startswith("prefect.asset.")]


def _first_event(worker: EventsWorker):
    events = _asset_events(worker)
    assert events, "No asset events were captured by the worker"
    return events[0]


def _materialization_events(events):
    """Filter events to only include asset materialization events."""
    return [e for e in events if e.event.startswith("prefect.asset.materialization")]


def _reference_events(events):
    """Filter events to only include asset reference events."""
    return [e for e in events if e.event.startswith("prefect.asset.referenced")]


def _event_with_resource_id(events, resource_id: str):
    for e in events:
        if e.resource.id == resource_id:
            return e
    else:
        raise ValueError(f"No events with resource_id: {resource_id}")


def _has_upstream_asset(event, upstream_asset_key: str) -> bool:
    return any(
        r["prefect.resource.id"] == upstream_asset_key
        and r["prefect.resource.role"] == "asset"
        for r in event.related
    )


def _has_related_of_role(event, role):
    return any(r["prefect.resource.role"] == role for r in event.related)


# =============================================================================
# Basic Asset Validation and Utilities
# =============================================================================


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


@pytest.mark.parametrize(
    "invalid_key",
    [
        "s3://bucket/file with space.csv",
        "s3://bucket/file\nwith\nnewlines.csv",
        "s3://bucket/file\twith\ttabs.csv",
        "s3://bucket/file#fragment.csv",
        "s3://bucket/file?query=param.csv",
        "s3://bucket/file&param=value.csv",
        "s3://bucket/file%encoded.csv",
        's3://bucket/file"quoted".csv',
        "s3://bucket/file'quoted'.csv",
        "s3://bucket/file<bracket>.csv",
        "s3://bucket/file[bracket].csv",
        "s3://bucket/file{brace}.csv",
        "s3://bucket/file|pipe.csv",
        "s3://bucket/file\\backslash.csv",
        "s3://bucket/file^caret.csv",
        "s3://bucket/file`backtick`.csv",
        "s3://bucket/file\r\ncarriage.csv",
        "s3://bucket/file\0null.csv",
    ],
)
def test_asset_restricted_characters(invalid_key):
    with pytest.raises(ValueError):
        Asset(key=invalid_key)


def test_asset_max_length():
    valid_key = "s3://bucket/" + "a" * (MAX_ASSET_KEY_LENGTH - len("s3://bucket/"))
    asset = Asset(key=valid_key)
    assert asset.key == valid_key

    invalid_key = "s3://bucket/" + "a" * (
        MAX_ASSET_KEY_LENGTH + 1 - len("s3://bucket/")
    )
    with pytest.raises(
        ValueError, match=f"Asset key cannot exceed {MAX_ASSET_KEY_LENGTH} characters"
    ):
        Asset(key=invalid_key)


def test_asset_length_edge_cases():
    # Test a few characters under the limit
    under_limit_key = "s3://bucket/" + "x" * (
        MAX_ASSET_KEY_LENGTH - 2 - len("s3://bucket/")
    )
    asset = Asset(key=under_limit_key)
    assert asset.key == under_limit_key

    # Test way over the limit
    way_over_key = "s3://bucket/" + "z" * 1000
    with pytest.raises(
        ValueError, match=f"Asset key cannot exceed {MAX_ASSET_KEY_LENGTH} characters"
    ):
        Asset(key=way_over_key)

    # Test minimum viable URI
    min_key = "s3://a"
    asset = Asset(key=min_key)
    assert asset.key == min_key


def test_asset_valid_characters():
    """Test that common valid characters work fine."""
    valid_keys = [
        "s3://bucket/folder/file.csv",
        "postgres://database/table",
        "file://local/path.txt",
        "custom://resource-with_underscores.data",
        "protocol://host:port/path",
        "scheme://user@host/resource",
        "s3://bucket/folder/file-name_123.parquet",
    ]

    for key in valid_keys:
        asset = Asset(key=key)
        assert asset.key == key


def test_asset_as_resource():
    asset = Asset(key="s3://bucket/data")
    resource = AssetContext.asset_as_resource(asset)
    assert resource["prefect.resource.id"] == "s3://bucket/data"


def test_asset_as_related():
    asset = Asset(key="postgres://prod/users")
    related = AssetContext.asset_as_related(asset)
    assert related["prefect.resource.id"] == "postgres://prod/users"
    assert related["prefect.resource.role"] == "asset"


def test_asset_as_resource_with_no_properties():
    asset = Asset(key="s3://bucket/data")
    resource = AssetContext.asset_as_resource(asset)

    assert resource == {"prefect.resource.id": "s3://bucket/data"}
    assert "prefect.resource.name" not in resource
    assert "prefect.asset.description" not in resource
    assert "prefect.asset.url" not in resource
    assert "prefect.asset.owners" not in resource


def test_asset_as_resource_with_partial_properties():
    asset = Asset(
        key="postgres://prod/users",
        properties=AssetProperties(name="Users Table", description="Main users table"),
    )
    resource = AssetContext.asset_as_resource(asset)

    expected = {
        "prefect.resource.id": "postgres://prod/users",
        "prefect.resource.name": "Users Table",
        "prefect.asset.description": "Main users table",
    }
    assert resource == expected
    assert "prefect.asset.url" not in resource
    assert "prefect.asset.owners" not in resource


def test_asset_as_resource_with_all_properties():
    asset = Asset(
        key="s3://data-lake/enriched/customers.parquet",
        properties=AssetProperties(
            name="Customer Data",
            description="Enriched customer dataset",
            url="https://dashboard.company.com/datasets/customers",
            owners=["data-team", "analytics"],
        ),
    )
    resource = AssetContext.asset_as_resource(asset)

    expected = {
        "prefect.resource.id": "s3://data-lake/enriched/customers.parquet",
        "prefect.resource.name": "Customer Data",
        "prefect.asset.description": "Enriched customer dataset",
        "prefect.asset.url": "https://dashboard.company.com/datasets/customers",
        "prefect.asset.owners": '["data-team", "analytics"]',
    }
    assert resource == expected


def test_asset_as_resource_excludes_unset_properties():
    """Test that asset_as_resource excludes properties that were not explicitly set."""
    asset = Asset(
        key="postgres://prod/transactions",
        properties=AssetProperties(
            name="Transactions",
            # description is not set (will be None)
            # url is not set (will be None)
            owners=["finance-team"],
        ),
    )
    resource = AssetContext.asset_as_resource(asset)

    # Should only include the fields that were explicitly set
    expected = {
        "prefect.resource.id": "postgres://prod/transactions",
        "prefect.resource.name": "Transactions",
        "prefect.asset.owners": '["finance-team"]',
    }
    assert resource == expected
    # Ensure unset fields are not included
    assert "prefect.asset.description" not in resource
    assert "prefect.asset.url" not in resource


def test_asset_description_max_length():
    # Test with description exactly at the limit
    exact_limit_description = "X" * MAX_ASSET_DESCRIPTION_LENGTH
    properties_exact = AssetProperties(description=exact_limit_description)
    assert len(properties_exact.description) == MAX_ASSET_DESCRIPTION_LENGTH
    assert properties_exact.description == exact_limit_description

    # Test with description under the limit
    short_description = "Short description"
    properties_short = AssetProperties(description=short_description)
    assert properties_short.description == short_description

    # Test with None description
    properties_none = AssetProperties(description=None)
    assert properties_none.description is None

    # Test that description longer than 5000 characters raises ValidationError
    long_description = "A" * (MAX_ASSET_DESCRIPTION_LENGTH + 1)

    with pytest.raises(
        ValueError,
        match=f"String should have at most {MAX_ASSET_DESCRIPTION_LENGTH} characters",
    ):
        AssetProperties(description=long_description)


# =============================================================================
# Single Asset Operations
# =============================================================================


@pytest.mark.usefixtures("reset_worker_events")
def test_single_asset_materialization_success(asserting_events_worker: EventsWorker):
    """Test single asset materialization success.

    Expected graph: [M: postgres://prod/users]
    """
    users = Asset(key="postgres://prod/users")

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
    assert any(r.id.startswith("prefect.flow-run.") for r in evt.related)


@pytest.mark.usefixtures("reset_worker_events")
def test_single_asset_materialization_failure(asserting_events_worker: EventsWorker):
    """Test single asset materialization failure.

    Expected graph: [M: s3://data/broken] (failed)
    """
    asset = Asset(key="s3://data/broken")

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


@pytest.mark.usefixtures("reset_worker_events")
def test_single_asset_reference(asserting_events_worker: EventsWorker):
    """Test single asset reference.

    Expected graph: [], without a materialization no reference is emitted
    """

    @task(asset_deps=["s3://bucket/raw_data.csv"])
    def read_data():
        return {"rows": 100}

    @flow
    def pipeline():
        read_data()

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    assert not events


@pytest.mark.usefixtures("reset_worker_events")
def test_multiple_asset_materializations(asserting_events_worker: EventsWorker):
    """Test multiple assets materialized by single function.

    Expected graph: [M: postgres://prod/users_raw], [M: postgres://prod/orders_raw]
    """
    user_asset = Asset(key="postgres://prod/users_raw")
    orders_asset = Asset(key="postgres://prod/orders_raw")

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


# =============================================================================
# String Key Conversion
# =============================================================================


@pytest.mark.usefixtures("reset_worker_events")
def test_mixed_asset_objects_and_string_keys(asserting_events_worker: EventsWorker):
    """Test that mixed Asset objects and string keys work together.

    This comprehensively tests string key conversion in both @materialize and @task(asset_deps).

    Expected graph:
    [R: postgres://db/users] --> [M: s3://bucket/final.parquet]
    [R: s3://bucket/raw.csv] --> [M: s3://bucket/summary.json]
    """
    # Mix Asset object and string in asset_deps
    asset_obj = Asset(key="postgres://db/users")

    @task(asset_deps=[asset_obj, "s3://bucket/raw.csv"])
    def read_mixed_deps():
        return {"data": "mixed"}

    # Mix Asset object and string in materialize
    output_asset = Asset(key="s3://bucket/final.parquet")

    @materialize(output_asset, "s3://bucket/summary.json")
    def write_mixed_outputs(data):
        return ({"final": True}, {"summary": True})

    @flow
    def pipeline():
        data = read_mixed_deps()
        write_mixed_outputs(data)

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    assert len(events) == 4  # 2 references + 2 materializations

    ref_events = _reference_events(events)
    mat_events = _materialization_events(events)

    assert len(ref_events) == 2
    assert len(mat_events) == 2

    # Check reference events include both Asset object and string key
    ref_keys = {evt.resource.id for evt in ref_events}
    assert ref_keys == {"postgres://db/users", "s3://bucket/raw.csv"}

    # Check materialization events include both Asset object and string key
    mat_keys = {evt.resource.id for evt in mat_events}
    assert mat_keys == {"s3://bucket/final.parquet", "s3://bucket/summary.json"}

    # Check that materialization events have the references as related assets
    for mat_evt in mat_events:
        related_asset_ids = {r.id for r in mat_evt.related if r.role == "asset"}
        assert "postgres://db/users" in related_asset_ids
        assert "s3://bucket/raw.csv" in related_asset_ids


# =============================================================================
# Linear Dependencies
# =============================================================================


@pytest.mark.usefixtures("reset_worker_events")
def test_materialization_to_materialization_dependency(
    asserting_events_worker: EventsWorker,
):
    """Test linear asset dependency between two materializations.

    Expected graph: [M: postgres://prod/users] --> [M: postgres://prod/users_clean]
    """
    upstream = Asset(key="postgres://prod/users")
    downstream = Asset(key="postgres://prod/users_clean")

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

    events = _asset_events(asserting_events_worker)
    assert len(events) == 3

    ref_events = _reference_events(events)
    mat_events = _materialization_events(events)

    assert len(ref_events) == 1
    assert len(mat_events) == 2

    assert _event_with_resource_id(ref_events, upstream.key)
    assert {mat.resource.id for mat in mat_events} == {upstream.key, downstream.key}

    downstream_mat = _event_with_resource_id(mat_events, downstream.key)
    assert _has_upstream_asset(downstream_mat, upstream.key)


@pytest.mark.usefixtures("reset_worker_events")
def test_reference_to_materialization_dependency(
    asserting_events_worker: EventsWorker,
):
    """Test linear dependency from reference to materialization.

    Expected graph: [R: postgres://prod/users] --> [M: postgres://prod/users_clean]
    """
    upstream = Asset(key="postgres://prod/users")
    downstream = Asset(key="postgres://prod/users_clean")

    @task(asset_deps=[upstream])
    def read():
        return {"rows": 1}

    @materialize(downstream)
    def load(data):
        return {"rows": 1}

    @flow
    def pipeline():
        data = read()
        load(data)

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    mat_events = _materialization_events(events)
    ref_events = _reference_events(events)

    assert len(mat_events) == 1
    assert len(ref_events) == 1

    mat_evt = _event_with_resource_id(mat_events, downstream.key)
    assert _has_upstream_asset(mat_evt, upstream.key)


@pytest.mark.usefixtures("reset_worker_events")
def test_linear_dependency_with_intermediate_task(
    asserting_events_worker: EventsWorker,
):
    """Test linear dependency with intermediate non-asset task.

    Expected graph: [M: s3://data/raw_data] --> [M: s3://data/processed_data]
    """
    upstream = Asset(key="s3://data/raw_data")
    downstream = Asset(key="s3://data/processed_data")

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
    assert len(events) == 3

    ref_events = _reference_events(events)
    mat_events = _materialization_events(events)

    assert _event_with_resource_id(ref_events, upstream.key)
    assert {mat.resource.id for mat in mat_events} == {upstream.key, downstream.key}

    downstream_mat = _event_with_resource_id(mat_events, downstream.key)
    assert _has_upstream_asset(downstream_mat, upstream.key)


@pytest.mark.usefixtures("reset_worker_events")
def test_materialize_with_explicit_asset_deps(asserting_events_worker: EventsWorker):
    """Test @materialize with explicit asset_deps parameter.

    Expected graph: [R: s3://bucket/raw_data.csv] --> [M: s3://bucket/data.csv]
    """

    @materialize("s3://bucket/data.csv", asset_deps=["s3://bucket/raw_data.csv"])
    def write_data():
        return {"rows": 100}

    @flow
    def pipeline():
        write_data()

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    assert len(events) == 2

    # Find reference and materialization events
    ref_events = _reference_events(events)
    mat_events = _materialization_events(events)

    assert len(ref_events) == 1
    assert len(mat_events) == 1

    # Check reference
    assert ref_events[0].resource.id == "s3://bucket/raw_data.csv"

    # Check materialization
    mat_evt = _event_with_resource_id(mat_events, "s3://bucket/data.csv")
    assert _has_upstream_asset(mat_evt, "s3://bucket/raw_data.csv")


@pytest.mark.usefixtures("reset_worker_events")
def test_three_stage_linear_pipeline(asserting_events_worker: EventsWorker):
    """Test three-stage linear pipeline with direct dependencies only.

    Expected graph: [M: s3://lake/bronze/users] --> [M: s3://lake/silver/users] --> [M: s3://lake/gold/users]
    """
    bronze = Asset(key="s3://lake/bronze/users")
    silver = Asset(key="s3://lake/silver/users")
    gold = Asset(key="s3://lake/gold/users")

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
    assert len(events) == 5  # 3 materializations + 2 reference events

    # Get materialization and reference events using helper functions
    mat_events = _materialization_events(events)
    ref_events = _reference_events(events)

    assert len(mat_events) == 3
    assert len(ref_events) == 2

    # Get specific materialization events using helper function
    evt_bronze = _event_with_resource_id(mat_events, bronze.key)
    evt_silver = _event_with_resource_id(mat_events, silver.key)
    evt_gold = _event_with_resource_id(mat_events, gold.key)

    # Bronze has no upstream dependencies
    assert not _has_related_of_role(evt_bronze, "asset")
    # Silver has bronze as upstream dependency
    assert _has_upstream_asset(evt_silver, bronze.key)
    # Gold has silver as upstream dependency
    assert _has_upstream_asset(evt_gold, silver.key)

    # Check that reference events are emitted for upstream assets
    ref_asset_ids = {e.resource.id for e in ref_events}
    assert ref_asset_ids == {bronze.key, silver.key}

    for e in (evt_bronze, evt_silver, evt_gold):
        assert any(r.id.startswith("prefect.flow-run.") for r in e.related)


# =============================================================================
# Complex Dependency Patterns
# =============================================================================


@pytest.mark.usefixtures("reset_worker_events")
def test_fan_in_dependency(asserting_events_worker: EventsWorker):
    """Test fan-in dependency pattern.
    
    Expected graph:
    [M: postgres://prod/users]     \
                                    --> [M: postgres://prod/user_orders_enriched]
    [M: postgres://prod/orders]    /
    """
    raw_users = Asset(key="postgres://prod/users")
    raw_orders = Asset(key="postgres://prod/orders")
    user_orders = Asset(key="postgres://prod/user_orders_enriched")

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
    assert len(events) == 5  # 3 materializations + 2 reference events

    mat_events = _materialization_events(events)
    ref_events = _reference_events(events)

    assert len(mat_events) == 3
    assert len(ref_events) == 2

    # Check reference events are emitted for upstream assets
    ref_asset_ids = {e.resource.id for e in ref_events}
    assert ref_asset_ids == {raw_users.key, raw_orders.key}

    # Check the downstream materialization event
    downstream_evt = _event_with_resource_id(mat_events, user_orders.key)
    assert _has_upstream_asset(downstream_evt, raw_users.key)
    assert _has_upstream_asset(downstream_evt, raw_orders.key)

    assert any(r.id.startswith("prefect.flow-run.") for r in downstream_evt.related)


@pytest.mark.usefixtures("reset_worker_events")
def test_fan_out_dependency(asserting_events_worker: EventsWorker):
    """Test fan-out dependency pattern.

    Expected graph:
                                   --> [M: s3://data/events_daily]
    [M: s3://data/events_raw]
                                   --> [M: s3://data/events_hourly]
    """
    events_raw = Asset(key="s3://data/events_raw")
    events_daily = Asset(key="s3://data/events_daily")
    events_hourly = Asset(key="s3://data/events_hourly")

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
    assert len(events) == 5  # 3 materializations + 2 reference events

    mat_events = _materialization_events(events)
    ref_events = _reference_events(events)

    assert len(mat_events) == 3
    assert len(ref_events) == 2

    # Check reference events are emitted for upstream assets (2 events for same asset)
    ref_asset_ids = {e.resource.id for e in ref_events}
    assert ref_asset_ids == {events_raw.key}
    assert len(ref_events) == 2  # Two reference events for the same upstream asset

    # Check the downstream materialization events
    daily_evt = _event_with_resource_id(mat_events, events_daily.key)
    hourly_evt = _event_with_resource_id(mat_events, events_hourly.key)

    assert _has_upstream_asset(daily_evt, events_raw.key)
    assert _has_upstream_asset(hourly_evt, events_raw.key)

    # Also check for flow-run context
    assert any(r.id.startswith("prefect.flow-run.") for r in daily_evt.related)
    assert any(r.id.startswith("prefect.flow-run.") for r in hourly_evt.related)


@pytest.mark.usefixtures("reset_worker_events")
def test_fan_in_to_fan_out_dependency(asserting_events_worker: EventsWorker):
    """Test fan-in to fan-out dependency pattern.

    Expected graph:
    [M: postgres://prod/users_raw]  ---> [M: postgres://prod/orders_per_user]
                                     |
    [M: postgres://prod/orders_raw] ---> [M: postgres://prod/orders_summary]
    """
    users_raw = Asset(key="postgres://prod/users_raw")
    orders_raw = Asset(key="postgres://prod/orders_raw")
    per_user = Asset(key="postgres://prod/orders_per_user")
    summary = Asset(key="postgres://prod/orders_summary")

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
    assert len(events) == 6  # 4 materializations + 2 reference events

    mat_events = _materialization_events(events)
    ref_events = _reference_events(events)

    assert len(mat_events) == 4
    assert len(ref_events) == 2

    # Check reference events are emitted for upstream assets
    ref_asset_ids = {e.resource.id for e in ref_events}
    assert ref_asset_ids == {users_raw.key, orders_raw.key}

    # Check each materialization event
    users_evt = _event_with_resource_id(mat_events, users_raw.key)
    orders_evt = _event_with_resource_id(mat_events, orders_raw.key)
    per_user_evt = _event_with_resource_id(mat_events, per_user.key)
    summary_evt = _event_with_resource_id(mat_events, summary.key)

    # Raw assets have no upstream dependencies
    assert not _has_related_of_role(users_evt, "asset")
    assert not _has_related_of_role(orders_evt, "asset")

    # Downstream assets have both raw assets as upstream dependencies
    assert _has_upstream_asset(per_user_evt, users_raw.key)
    assert _has_upstream_asset(per_user_evt, orders_raw.key)
    assert _has_upstream_asset(summary_evt, users_raw.key)
    assert _has_upstream_asset(summary_evt, orders_raw.key)

    # Also check for flow-run context
    for evt in [users_evt, orders_evt, per_user_evt, summary_evt]:
        assert any(r.id.startswith("prefect.flow-run.") for r in evt.related)


@pytest.mark.usefixtures("reset_worker_events")
def test_forward_propagation_asset_lineage(asserting_events_worker: EventsWorker):
    """Test that asset lineage flows forward through task graph without backward traversal.
    
    Expected graph:
    [R: s3://bucket/raw.csv]        \
                                     --> [M: s3://bucket/final.csv]
    [R: postgres://prod/users]      /
    """

    @task(asset_deps=["s3://bucket/raw.csv"])
    def extract():
        return {"data": "raw"}

    @task(asset_deps=["postgres://prod/users"])
    def transform(data):
        return {"data": "transformed"}

    @materialize("s3://bucket/final.csv")
    def load(data):
        return {"data": "final"}

    @flow
    def etl_pipeline():
        raw = extract()
        transformed = transform(raw)
        load(transformed)

    etl_pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    assert len(events) == 3

    # Find all event types
    ref_events = _reference_events(events)
    mat_events = _materialization_events(events)

    assert len(ref_events) == 2  # Two reference events
    assert len(mat_events) == 1  # One materialization event

    # Check references
    refs_resources = {e.resource.id for e in ref_events}
    assert "s3://bucket/raw.csv" in refs_resources
    assert "postgres://prod/users" in refs_resources

    # Check materialization - should include both upstream assets as related
    mat_event = mat_events[0]
    assert mat_event.resource.id == "s3://bucket/final.csv"

    # The materialization should have both upstream assets as related
    related_asset_ids = {r.id for r in mat_event.related if r.role == "asset"}
    assert "s3://bucket/raw.csv" in related_asset_ids
    assert "postgres://prod/users" in related_asset_ids


@pytest.mark.usefixtures("reset_worker_events")
def test_complex_snowflake_aggregation(asserting_events_worker: EventsWorker):
    """Test complex Snowflake aggregation pattern with multiple references and materializations.
    
    Expected graph:
    [R: .../table-1-raw] --> [M: .../table-1-cleaned] \
    [R: .../table-2-raw] --> [M: .../table-2-cleaned]  --> [M: .../aggregated-table]
    [R: .../table-3-raw] --> [M: .../table-3-cleaned] /
    """
    SNOWFLAKE_SCHEMA = "snowflake://my-database/my-schema"

    @task(asset_deps=[Asset(key=f"{SNOWFLAKE_SCHEMA}/table-1-raw")])
    def table_1_raw():
        return "fake data 1"

    @task(asset_deps=[Asset(key=f"{SNOWFLAKE_SCHEMA}/table-2-raw")])
    def table_2_raw():
        return "fake data 2"

    @task(asset_deps=[Asset(key=f"{SNOWFLAKE_SCHEMA}/table-3-raw")])
    def table_3_raw():
        return "fake data 3"

    table_1_cleaned_asset = Asset(key=f"{SNOWFLAKE_SCHEMA}/table-1-cleaned")
    table_2_cleaned_asset = Asset(key=f"{SNOWFLAKE_SCHEMA}/table-2-cleaned")
    table_3_cleaned_asset = Asset(key=f"{SNOWFLAKE_SCHEMA}/table-3-cleaned")

    @materialize(table_1_cleaned_asset)
    def table_1_cleaned(raw_table_1):
        return f"cleaned {raw_table_1}"

    @materialize(table_2_cleaned_asset)
    def table_2_cleaned(raw_table_2):
        return f"cleaned {raw_table_2}"

    @materialize(table_3_cleaned_asset)
    def table_3_cleaned(raw_table_3):
        return f"cleaned {raw_table_3}"

    aggregated_asset = Asset(key=f"{SNOWFLAKE_SCHEMA}/aggregated-table")

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
    assert len(events) == 10  # 4 materializations + 6 reference events

    mat_events = _materialization_events(events)
    ref_events = _reference_events(events)

    assert len(mat_events) == 4
    assert len(ref_events) == 6

    by_id = {e.resource.id: e for e in events}

    # Check reference events for raw assets (direct asset dependencies)
    for raw_key in (
        f"{SNOWFLAKE_SCHEMA}/table-1-raw",
        f"{SNOWFLAKE_SCHEMA}/table-2-raw",
        f"{SNOWFLAKE_SCHEMA}/table-3-raw",
    ):
        evt = by_id[raw_key]
        assert evt.event == "prefect.asset.referenced"
        assert not _has_related_of_role(evt, "asset")

    # Check materialization events for cleaned assets
    for cleaned_key, raw_key in [
        (table_1_cleaned_asset.key, f"{SNOWFLAKE_SCHEMA}/table-1-raw"),
        (table_2_cleaned_asset.key, f"{SNOWFLAKE_SCHEMA}/table-2-raw"),
        (table_3_cleaned_asset.key, f"{SNOWFLAKE_SCHEMA}/table-3-raw"),
    ]:
        evt = _event_with_resource_id(mat_events, cleaned_key)
        assert _has_upstream_asset(evt, raw_key)

    # Check aggregated materialization event
    agg_evt = _event_with_resource_id(mat_events, aggregated_asset.key)
    assert _has_upstream_asset(agg_evt, table_1_cleaned_asset.key)
    assert _has_upstream_asset(agg_evt, table_2_cleaned_asset.key)
    assert _has_upstream_asset(agg_evt, table_3_cleaned_asset.key)

    for e in events:
        assert any(r.id.startswith("prefect.flow-run.") for r in e.related)


# =============================================================================
# Advanced Execution Patterns
# =============================================================================


@pytest.mark.usefixtures("reset_worker_events")
async def test_async_materialization(asserting_events_worker: EventsWorker):
    """Test async asset materialization.

    Expected graph: [M: postgres://prod/async]
    """
    asset = Asset(key="postgres://prod/async")

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


@pytest.mark.usefixtures("reset_worker_events")
def test_cached_asset_does_not_emit_duplicate_events(
    asserting_events_worker: EventsWorker,
):
    """Test that cached assets don't emit duplicate events.

    Expected graph: [M: s3://bucket/cached-data] (only first execution, second is cached)
    """
    asset = Asset(key="s3://bucket/cached-data")

    @materialize(asset, persist_result=True)
    def make_data():
        return {"rows": 100}

    @flow
    def pipeline():
        # First run - should emit materialization event
        make_data()
        # Second run - should use cache and NOT emit event
        make_data()

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)

    assert len(events) == 1
    assert events[0].event == "prefect.asset.materialization.succeeded"
    assert events[0].resource.id == asset.key


@pytest.mark.usefixtures("reset_worker_events")
def test_linear_dependency_with_submit(asserting_events_worker):
    """Test linear dependency using task.submit().

    Expected graph: [R: postgres://prod/users_submit] --> [M: postgres://prod/users_clean_submit]
    """
    upstream = Asset(key="postgres://prod/users_submit")
    downstream = Asset(key="postgres://prod/users_clean_submit")

    @task(asset_deps=[upstream])
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
    downstream_evt = _event_with_resource_id(events, downstream.key)
    assert _has_upstream_asset(downstream_evt, upstream.key)
    assert _has_related_of_role(downstream_evt, "flow-run")


@pytest.mark.usefixtures("reset_worker_events")
def test_map_with_asset_dependency(asserting_events_worker):
    """Test map operation with asset dependency.

    Expected graph:

    [R: s3://data/source_data]   --> [M: s3://data/processed] (latest of task 1, 2, 3)
    """
    source_asset = Asset(key="s3://data/source_data")
    destination_asset = Asset(key="s3://data/processed")

    @task(asset_deps=[source_asset])
    def extract_source():
        return ["item1", "item2", "item3"]

    @materialize(destination_asset)
    def process_item(item):
        return {"processed": item}

    @flow
    def pipeline():
        source_data = extract_source()
        futures = process_item.map(source_data)
        for future in futures:
            future.wait()

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)

    assert len(events) == 6

    source_events = [e for e in events if e.resource.id == source_asset.key]
    assert len(source_events) == 3

    destination_events = [e for e in events if e.resource.id == destination_asset.key]
    assert len(destination_events) == 3

    for evt in destination_events:
        assert evt.event == "prefect.asset.materialization.succeeded"
        assert _has_upstream_asset(evt, source_asset.key)
        assert _has_related_of_role(evt, "flow-run")


@pytest.mark.usefixtures("reset_worker_events")
def test_asset_dependency_with_wait_for(asserting_events_worker):
    """Test asset dependency using wait_for parameter.

    Expected graph: [R: s3://data/dependencies/source] --> [M: s3://data/dependencies/dependent]
    """
    source_asset = Asset(key="s3://data/dependencies/source")
    dependent_asset = Asset(key="s3://data/dependencies/dependent")

    @task(asset_deps=[source_asset])
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

    dependent_evt = _event_with_resource_id(events, dependent_asset.key)
    assert _has_upstream_asset(dependent_evt, source_asset.key)
    assert _has_related_of_role(dependent_evt, "flow-run")


# =============================================================================
# @materialize(... by=...)
# =============================================================================


@pytest.mark.usefixtures("reset_worker_events")
def test_materialization_with_by_parameter(asserting_events_worker: EventsWorker):
    """Test that @materialize with by parameter includes materialized-by tool as related resource.

    Expected graph: [M: s3://bucket/dbt_table] (materialized by dbt)
    """
    asset = Asset(key="s3://bucket/dbt_table")

    @materialize(asset, by="dbt")
    def create_dbt_table():
        return {"rows": 100}

    @flow
    def pipeline():
        create_dbt_table()

    pipeline()
    asserting_events_worker.drain()

    evt = _first_event(asserting_events_worker)
    assert evt.event == "prefect.asset.materialization.succeeded"
    assert evt.resource.id == asset.key

    assert _has_related_of_role(evt, "asset-materialized-by")
    materialized_by_resources = [
        r for r in evt.related if r.role == "asset-materialized-by"
    ]
    assert len(materialized_by_resources) == 1
    assert materialized_by_resources[0].id == "dbt"


@pytest.mark.usefixtures("reset_worker_events")
def test_materialization_with_by_parameter_and_dependencies(
    asserting_events_worker: EventsWorker,
):
    """Test materialization with by parameter includes tool alongside asset dependencies.

    Expected graph: [R: postgres://prod/raw_users] --> [M: s3://warehouse/users] (materialized by spark)
    """
    source_asset = Asset(key="postgres://prod/raw_users")
    target_asset = Asset(key="s3://warehouse/users")

    @task(asset_deps=[source_asset])
    def extract_users():
        return {"users": 500}

    @materialize(target_asset, by="spark")
    def transform_users(raw_data):
        return {"processed_users": raw_data["users"]}

    @flow
    def pipeline():
        raw_data = extract_users()
        transform_users(raw_data)

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    assert len(events) == 2

    # Find the materialization event
    mat_events = _materialization_events(events)
    assert len(mat_events) == 1
    mat_evt = mat_events[0]

    assert mat_evt.resource.id == target_asset.key

    related_by_role = {r.role: r.id for r in mat_evt.related}

    assert "asset" in related_by_role
    assert related_by_role["asset"] == source_asset.key

    assert "asset-materialized-by" in related_by_role
    assert related_by_role["asset-materialized-by"] == "spark"


# =============================================================================
# Duplicate Asset Prevention
# =============================================================================


@pytest.mark.usefixtures("reset_worker_events")
def test_materialize_prevents_duplicate_assets(asserting_events_worker: EventsWorker):
    """Test that @materialize prevents duplicate assets in args and asset_deps."""
    asset1 = Asset(key="s3://bucket/data1.csv")
    asset2 = Asset(key="s3://bucket/data2.csv")

    # Test duplicate assets as positional arguments
    @materialize(asset1, asset1, asset2)  # asset1 appears twice
    def make_data_with_duplicate_args():
        return ({"rows": 100}, {"rows": 100}, {"rows": 200})

    # Test duplicate assets in asset_deps
    @materialize(
        "s3://bucket/output.csv",
        asset_deps=[asset1, asset1, asset2],  # asset1 appears twice
    )
    def make_data_with_duplicate_deps():
        return {"rows": 300}

    @flow
    def pipeline():
        make_data_with_duplicate_args()
        make_data_with_duplicate_deps()

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    mat_events = _materialization_events(events)
    ref_events = _reference_events(events)

    # Should only have unique materialization events (no duplicates)
    mat_keys = {evt.resource.id for evt in mat_events}
    assert mat_keys == {asset1.key, asset2.key, "s3://bucket/output.csv"}

    # Should only have unique reference events (no duplicates)
    ref_keys = {evt.resource.id for evt in ref_events}
    assert ref_keys == {asset1.key, asset2.key}

    # Verify exact count - duplicates should be eliminated
    assert len(mat_events) == 3  # asset1, asset2, output.csv (no duplicate asset1)
    assert len(ref_events) == 2  # asset1, asset2 (no duplicate asset1)


@pytest.mark.usefixtures("reset_worker_events")
def test_task_asset_deps_prevents_duplicates(asserting_events_worker: EventsWorker):
    """Test that @task asset_deps prevents duplicate assets."""
    asset1 = Asset(key="postgres://db/table1")
    asset2 = Asset(key="postgres://db/table2")

    # Test duplicate assets in asset_deps using mix of Asset objects and strings
    @task(
        asset_deps=[
            asset1,
            "postgres://db/table1",  # Same as asset1 but as string
            asset2,
            asset2,  # Direct duplicate
        ]
    )
    def read_data():
        return {"data": "processed"}

    @materialize("s3://output/result.csv")
    def save_data(data):
        return {"rows": 100}

    @flow
    def pipeline():
        data = read_data()
        save_data(data)

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    ref_events = _reference_events(events)
    mat_events = _materialization_events(events)

    # Should only have unique reference events (duplicates eliminated)
    ref_keys = {evt.resource.id for evt in ref_events}
    assert ref_keys == {asset1.key, asset2.key}

    # Should have exactly 2 reference events (no duplicates)
    assert len(ref_events) == 2

    # Should have 1 materialization event
    assert len(mat_events) == 1
    assert mat_events[0].resource.id == "s3://output/result.csv"

    # The materialization should have both unique upstream assets
    mat_evt = mat_events[0]
    related_asset_ids = {r.id for r in mat_evt.related if r.role == "asset"}
    assert related_asset_ids == {asset1.key, asset2.key}


# =============================================================================
# Metadata
# =============================================================================


@pytest.mark.usefixtures("reset_worker_events")
def test_linear_dependency_with_asset_properties(asserting_events_worker: EventsWorker):
    """Test linear dependency from reference to materialization where both assets have properties.

    Expected graph: [R: s3://lake/raw/customer_data.parquet] --> [M: postgres://warehouse/customers]
    """
    source_asset = Asset(
        key="s3://lake/raw/customer_data.parquet",
        properties=AssetProperties(
            name="Raw Customer Data",
            description="Raw customer data from external source",
            url="https://dashboard.company.com/datasets/raw-customers",
            owners=["data-ingestion-team"],
        ),
    )

    target_asset = Asset(
        key="postgres://warehouse/customers",
        properties=AssetProperties(
            name="Customer Table",
            description="Processed customer data in warehouse",
            url="https://dashboard.company.com/tables/customers",
            owners=["data-team", "analytics-team"],
        ),
    )

    @task(asset_deps=[source_asset])
    def extract_customers():
        return {"rows": 1000, "extracted": True}

    @materialize(target_asset)
    def load_customers(data):
        return {"rows": data["rows"], "processed": True}

    @flow
    def customer_pipeline():
        raw_data = extract_customers()
        load_customers(raw_data)

    customer_pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    assert len(events) == 2

    ref_events = _reference_events(events)
    mat_events = _materialization_events(events)

    assert len(ref_events) == 1
    assert len(mat_events) == 1

    ref_evt = ref_events[0]
    assert ref_evt.resource.id == source_asset.key
    assert ref_evt.event == "prefect.asset.referenced"

    mat_evt = mat_events[0]
    assert mat_evt.resource.id == target_asset.key
    assert mat_evt.event == "prefect.asset.materialization.succeeded"

    assert _has_upstream_asset(mat_evt, source_asset.key)

    assert _has_related_of_role(ref_evt, "flow-run")
    assert _has_related_of_role(mat_evt, "flow-run")


@pytest.mark.usefixtures("reset_worker_events")
def test_materialization_metadata(asserting_events_worker: EventsWorker):
    """Test that metadata is still captured when a materializing task succeeds."""

    asset = Asset(key="s3://bucket/data.csv")

    @materialize(asset)
    def my_task():
        asset.add_metadata({"wrote_rows": 1000})

    @flow
    def pipeline():
        my_task()

    pipeline()
    asserting_events_worker.drain()

    event = _first_event(asserting_events_worker)
    assert event.event == "prefect.asset.materialization.succeeded"
    assert event.resource.id == "s3://bucket/data.csv"
    assert event.payload == {"wrote_rows": 1000}


@pytest.mark.usefixtures("reset_worker_events")
def test_materialization_metadata_str_utility(asserting_events_worker: EventsWorker):
    """Test that metadata is still captured when a materializing task succeeds."""
    from prefect.assets import add_asset_metadata

    @materialize("s3://bucket/data.csv")
    def my_task():
        add_asset_metadata("s3://bucket/data.csv", {"wrote_rows": 1000})

    @flow
    def pipeline():
        my_task()

    pipeline()
    asserting_events_worker.drain()

    event = _first_event(asserting_events_worker)
    assert event.event == "prefect.asset.materialization.succeeded"
    assert event.resource.id == "s3://bucket/data.csv"
    assert event.payload == {"wrote_rows": 1000}


@pytest.mark.usefixtures("reset_worker_events")
def test_stacking_materialization_metadata(asserting_events_worker: EventsWorker):
    """Test that metadata is still captured when a materializing task succeeds."""

    asset = Asset(key="s3://bucket/data.csv")

    @materialize(asset)
    def my_task():
        asset.add_metadata({"wrote_rows": 1000})
        asset.add_metadata({"wrote_columns": 5})

    @flow
    def pipeline():
        my_task()

    pipeline()
    asserting_events_worker.drain()

    event = _first_event(asserting_events_worker)
    assert event.event == "prefect.asset.materialization.succeeded"
    assert event.resource.id == "s3://bucket/data.csv"
    assert event.payload == {"wrote_rows": 1000, "wrote_columns": 5}


@pytest.mark.usefixtures("reset_worker_events")
def test_materialization_metadata_multiple_assets(
    asserting_events_worker: EventsWorker,
):
    """Test that metadata is still captured when a materializing task succeeds."""

    asset1 = Asset(key="s3://bucket/data1.csv")
    asset2 = Asset(key="s3://bucket/data2.csv")

    @materialize(asset1, asset2)
    def my_task():
        asset1.add_metadata({"wrote_rows": 1000})
        asset2.add_metadata({"wrote_columns": 5})

    @flow
    def pipeline():
        my_task()

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)

    event1 = next(
        (
            e
            for e in events
            if e.event == "prefect.asset.materialization.succeeded"
            and e.resource.id == "s3://bucket/data1.csv"
        ),
        None,
    )
    assert event1 is not None
    assert event1.payload == {"wrote_rows": 1000}

    event2 = next(
        (
            e
            for e in events
            if e.event == "prefect.asset.materialization.succeeded"
            and e.resource.id == "s3://bucket/data2.csv"
        ),
        None,
    )
    assert event2 is not None
    assert event2.payload == {"wrote_columns": 5}


@pytest.mark.usefixtures("reset_worker_events")
def test_materialization_metadata_with_task_failure(
    asserting_events_worker: EventsWorker,
):
    """Test that metadata is still captured when a task fails."""

    asset = Asset(key="s3://bucket/failed_output.csv")

    @materialize(asset)
    def failing_task():
        asset.add_metadata({"attempted_rows": 1000})
        raise RuntimeError("Processing failed")

    @flow
    def pipeline():
        try:
            failing_task()
        except RuntimeError:
            pass

    pipeline()
    asserting_events_worker.drain()

    event = _first_event(asserting_events_worker)
    assert event.event == "prefect.asset.materialization.failed"
    assert event.resource.id == "s3://bucket/failed_output.csv"
    assert event.payload == {"attempted_rows": 1000}


def test_add_asset_metadata_throws_error_for_invalid_asset_key():
    """Test that add_asset_metadata throws ValueError for asset keys not in downstream_assets."""
    from prefect.assets import add_asset_metadata

    # Test case 1: Valid asset key should work
    valid_asset = Asset(key="s3://bucket/valid_data.csv")

    @materialize(valid_asset)
    def valid_task():
        # This should work - asset is in downstream_assets
        add_asset_metadata("s3://bucket/valid_data.csv", {"rows": 100})
        return {"success": True}

    @flow
    def valid_pipeline():
        valid_task()

    # This should not raise an error
    valid_pipeline()

    # Test case 2: Invalid asset key should throw error
    materialized_asset = Asset(key="s3://bucket/materialized.csv")

    @materialize(materialized_asset)
    def invalid_task():
        # This should fail - different asset key not in downstream_assets
        add_asset_metadata("s3://bucket/different_asset.csv", {"rows": 200})
        return {"success": False}

    @flow
    def invalid_pipeline():
        invalid_task()

    # This should raise a ValueError
    with pytest.raises(
        ValueError,
        match="Can only add metadata to assets that are arguments to @materialize",
    ):
        invalid_pipeline()

    # Test case 3: Non-materializing task should throw error
    @task
    def non_materializing_task():
        # This should fail - no downstream_assets in a regular task
        add_asset_metadata("s3://bucket/any_asset.csv", {"rows": 300})
        return {"success": False}

    @flow
    def non_materializing_pipeline():
        non_materializing_task()

    # This should raise a ValueError
    with pytest.raises(
        ValueError,
        match="Can only add metadata to assets that are arguments to @materialize",
    ):
        non_materializing_pipeline()


@pytest.mark.usefixtures("reset_worker_events")
def test_nested_materialization(asserting_events_worker: EventsWorker):
    """Test nested materialization - a materialize task called inside another materialize task.

    Expected behavior: Both materializations should emit events, but there should be
    no relationship between the two assets.

    Expected graph: [M: s3://bucket/outer.csv], [M: s3://bucket/inner.csv] (no connection)
    """
    outer_asset = Asset(key="s3://bucket/outer.csv")
    inner_asset = Asset(key="s3://bucket/inner.csv")

    @materialize(inner_asset)
    def inner_task():
        return {"inner_data": "processed"}

    @materialize(outer_asset)
    def outer_task():
        inner_result = inner_task()
        return {"outer_data": "wrapped", "inner_result": inner_result}

    @flow
    def pipeline():
        outer_task()

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    mat_events = _materialization_events(events)

    # Should have exactly 2 materialization events
    assert len(mat_events) == 2

    # Get the specific events
    outer_evt = _event_with_resource_id(mat_events, outer_asset.key)
    inner_evt = _event_with_resource_id(mat_events, inner_asset.key)

    # Both should be successful materializations
    assert outer_evt.event == "prefect.asset.materialization.succeeded"
    assert inner_evt.event == "prefect.asset.materialization.succeeded"

    # Check that neither asset has the other as a related asset
    outer_related_assets = {r.id for r in outer_evt.related if r.role == "asset"}
    inner_related_assets = {r.id for r in inner_evt.related if r.role == "asset"}

    # Inner asset should not be in outer's related assets
    assert inner_asset.key not in outer_related_assets

    # Outer asset should not be in inner's related assets
    assert outer_asset.key not in inner_related_assets

    # Both should have flow-run context
    assert any(r.id.startswith("prefect.flow-run.") for r in outer_evt.related)
    assert any(r.id.startswith("prefect.flow-run.") for r in inner_evt.related)


@pytest.mark.usefixtures("reset_worker_events")
def test_materialization_from_regular_task(asserting_events_worker: EventsWorker):
    """Test that a @materialize task called from inside a regular @task works correctly.

    Expected behavior: The materialization should emit an event, but no reference event
    should be emitted since the asset dependency is on the regular task, not the materialization.

    Expected graph: [M: s3://bucket/output.csv] (no reference event)
    """
    source_asset = Asset(key="postgres://db/source")
    output_asset = Asset(key="s3://bucket/output.csv")

    @materialize(output_asset)
    def materialize_data(data):
        return {"rows": data["transformed_rows"]}

    @task(asset_deps=[source_asset])
    def transform_data():
        transformed = {"transformed_rows": 100}
        result = materialize_data(transformed)
        return result

    @flow
    def pipeline():
        transform_data()

    pipeline()
    asserting_events_worker.drain()

    events = _asset_events(asserting_events_worker)
    ref_events = _reference_events(events)
    mat_events = _materialization_events(events)

    # Should have no reference events and 1 materialization event
    assert len(ref_events) == 0
    assert len(mat_events) == 1

    # Check materialization event
    mat_evt = mat_events[0]
    assert mat_evt.resource.id == output_asset.key
    assert mat_evt.event == "prefect.asset.materialization.succeeded"

    # The materialization should NOT have the source asset as an upstream dependency
    # since the dependency was on the regular task, not the materialization
    assert not _has_upstream_asset(mat_evt, source_asset.key)

    # Should have flow-run context
    assert any(r.id.startswith("prefect.flow-run.") for r in mat_evt.related)
