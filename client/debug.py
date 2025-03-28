try:
    from prefect import flow, task  # noqa: F401
except ImportError as e:
    print(f"Error: {e}")

    # Show what's available in the prefect module
    import prefect

    print("Available in prefect module:", dir(prefect))

    # Try to import separately to see which one fails
    try:
        from prefect import flow  # noqa: F401
    except ImportError as e1:
        print(f"Flow import error: {e1}")

    try:
        from prefect import task  # noqa: F401
    except ImportError as e2:
        print(f"Task import error: {e2}")
