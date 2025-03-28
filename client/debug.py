# Add this before the import that's failing
def trace_import(name, globals=None, locals=None, fromlist=(), level=0):
    print(f"Importing {name} (fromlist={fromlist}, level={level})")
    result = original_import(name, globals, locals, fromlist, level)
    print(f"Successfully imported {name}")
    return result


original_import = __import__
__builtins__["__import__"] = trace_import

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
