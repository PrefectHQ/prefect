"""
Fixtures for tests/results/ module.

This module is excluded from the clear_db auto-mark, meaning the database is not
cleared before each test. Block type slug conflicts are prevented by tests/blocks
using unique slugs via the unique_block_slug fixture.
"""
