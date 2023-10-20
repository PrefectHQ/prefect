try:
    from prefect.server.api.server import SERVER_API_VERSION
except ImportError:
    # support the case where server components are not available
    SERVER_API_VERSION = "0.8.4"
