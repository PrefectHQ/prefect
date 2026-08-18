import importlib.util
import os
import sys
from types import ModuleType
import unittest
from unittest.mock import MagicMock

# Mock base Block and pydantic if necessary for isolated test run
if "prefect.blocks.core" not in sys.modules:
    core_mod = ModuleType("prefect.blocks.core")
    class Block:
        def __init__(self, **data):
            for k, v in data.items(): setattr(self, k, v)
    core_mod.Block = Block
    sys.modules["prefect.blocks.core"] = core_mod

if "pydantic" not in sys.modules:
    pydantic_mod = ModuleType("pydantic")
    pydantic_mod.Field = lambda *args, **kwargs: kwargs.get("default", None)
    sys.modules["pydantic"] = pydantic_mod

# Direct module load
file_path = os.path.join(
    os.path.dirname(__file__),
    "../../src/prefect/blocks/action_gate.py",
)
spec = importlib.util.spec_from_file_location("prefect_action_gate", file_path)
action_gate_mod = importlib.util.module_from_spec(spec)
sys.modules["prefect_action_gate"] = action_gate_mod
spec.loader.exec_module(action_gate_mod)

ActionGateBlock = action_gate_mod.ActionGateBlock
GENESIS_HASH = action_gate_mod.GENESIS_HASH


class TestActionGateBlock(unittest.TestCase):
    def setUp(self):
        self.block = ActionGateBlock(
            never_equate_intent_to_approval=True,
            enforce_action_boundary=True,
        )

    def test_verify_task_action_allowed(self):
        res = self.block.verify_task_action(
            tool_name="sync_s3_bucket",
            payload={"bucket": "data-lake"},
            is_destructive=False,
        )
        self.assertTrue(res["allowed"])
        self.assertIn("hash", res)
        entries = self.block.get_ledger_entries()
        self.assertEqual(len(entries), 1)

    def test_verify_destructive_action_requires_confirmation(self):
        with self.assertRaises(PermissionError):
            self.block.verify_task_action(
                tool_name="drop_table",
                payload={"table": "analytics_prod"},
                is_destructive=True,
                user_confirmed=False,
            )

    def test_verify_destructive_action_with_confirmation(self):
        res = self.block.verify_task_action(
            tool_name="drop_table",
            payload={"table": "analytics_staging"},
            is_destructive=True,
            user_confirmed=True,
        )
        self.assertTrue(res["allowed"])
        entries = self.block.get_ledger_entries()
        self.assertEqual(len(entries), 1)

    def test_hash_chain_integrity(self):
        self.block.verify_task_action("step_1", {"p": 1})
        self.block.verify_task_action("step_2", {"p": 2})
        self.block.verify_task_action("step_3", {"p": 3})

        entries = self.block.get_ledger_entries()
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["prev_hash"], GENESIS_HASH)
        self.assertEqual(entries[1]["prev_hash"], entries[0]["curr_hash"])
        self.assertEqual(entries[2]["prev_hash"], entries[1]["curr_hash"])
        self.assertTrue(self.block.verify_ledger_integrity())


if __name__ == "__main__":
    unittest.main()
