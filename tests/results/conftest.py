"""
Fixtures for tests/results/ module.

This module is excluded from the clear_db auto-mark, meaning the database is not
cleared before each test. Block type slug conflicts are prevented by tests/blocks
and tests/public/results using unique slugs via UUID-prefixed names.

Note: We intentionally do NOT clear block documents here because doing so would
cause race conditions with tests in other modules (like tests/utilities) that
create and use block documents concurrently during parallel test execution.
"""
