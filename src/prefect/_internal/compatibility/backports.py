"""Functionality we want to use from later Python versions."""

try:
    import tomllib  # 3.11+
except ImportError:
    import toml as tomllib  # fallback on Python <3.11

    tomllib.TOMLDecodeError = tomllib.TomlDecodeError


__all__ = ["tomllib"]
