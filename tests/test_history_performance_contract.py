"""History optimization preserves JSON semantics and the 80-state contract."""

import json
import unittest
from unittest.mock import patch

import editor_session as session


class HistoryPerformanceContractTests(unittest.TestCase):
    def test_numeric_types_and_signed_zero_remain_distinct_changes(self):
        history = session.UndoHistory()
        values = (True, 1, 1.0, False, 0, 0.0, -0.0)
        for value in values:
            self.assertTrue(history.record({"value": value}))
            self.assertFalse(history.record({"value": value}))
        self.assertEqual(len(history._states), len(values))
        self.assertEqual(history.undo()["value"].hex(), (0.0).hex())

    def test_json_normalization_keeps_tuple_list_and_key_order_noops(self):
        history = session.UndoHistory()
        history.reset({"a": (1, 2), "b": "汉字"})
        self.assertFalse(history.record({"b": "汉字", "a": [1, 2]}))
        self.assertEqual(len(history._states), 1)

    def test_record_serializes_only_once_and_still_copies(self):
        history = session.UndoHistory()
        history.reset({"values": [1]})
        dumps = json.dumps
        with patch.object(session.json, "dumps", wraps=dumps) as serialize:
            self.assertFalse(history.record({"values": [1]}))
            self.assertEqual(serialize.call_count, 1)
            self.assertTrue(history.record({"values": [2]}))
            self.assertEqual(serialize.call_count, 2)

    def test_default_history_retains_original_80_states_and_independent_returns(self):
        history = session.UndoHistory()
        state = {"entries": [{"title": "before"}], "step": 0}
        for step in range(100):
            state["step"] = step
            self.assertTrue(history.record(state))
        state["entries"][0]["title"] = "caller changed"
        self.assertEqual(len(history._states), 80)
        self.assertEqual(history._states[0]["step"], 20)
        current = history.undo()
        current["entries"][0]["title"] = "returned changed"
        self.assertEqual(history.redo()["entries"][0]["title"], "before")

    def test_invalid_json_cannot_discard_redo_branch_or_move_cursor(self):
        history = session.UndoHistory()
        history.reset({"value": 1})
        history.record({"value": 2})
        history.undo()
        old_states, old_cursor = history._states.copy(), history._cursor
        for value in (float("inf"), float("nan"), object(), {1: "nonstring key"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                history.record({"value": value})
            self.assertEqual(history._states, old_states)
            self.assertEqual(history._cursor, old_cursor)
            self.assertTrue(history.can_redo)


if __name__ == "__main__":
    unittest.main()
