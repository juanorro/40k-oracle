"""Tests for collection bookkeeping."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import collection  # noqa: E402


class OwnedModels(unittest.TestCase):
    def test_the_same_unit_listed_twice_is_added_up(self):
        entries = [{"faction": "Death Guard", "unit": "Plague Marines", "models": 10},
                   {"faction": "Death Guard", "unit": "Plague Marines", "models": 5}]
        totals = collection.owned_models(entries)
        self.assertEqual(totals[("Death Guard", "Plague Marines")], 15)

    def test_different_units_stay_separate(self):
        entries = [{"faction": "Death Guard", "unit": "Typhus", "models": 1},
                   {"faction": "Death Guard", "unit": "Nurglings", "models": 6}]
        self.assertEqual(len(collection.owned_models(entries)), 2)

    def test_a_missing_count_is_zero(self):
        totals = collection.owned_models([{"faction": "Orks", "unit": "Boyz"}])
        self.assertEqual(totals[("Orks", "Boyz")], 0)

    def test_an_empty_collection(self):
        self.assertEqual(collection.owned_models([]), {})


@unittest.skipUnless((Path(__file__).resolve().parent.parent / "index.db").exists(),
                     "run scripts/build.py first")
class AgainstTheDatabase(unittest.TestCase):
    def setUp(self):
        import query
        self.con = query.connect()

    def test_points_use_the_bracket_covering_the_models_owned(self):
        five = collection.unit_points(self.con, "Chaos - Death Guard", "Plague Marines", 5)
        ten = collection.unit_points(self.con, "Chaos - Death Guard", "Plague Marines", 10)
        self.assertLess(five, ten)

    def test_more_models_than_any_bracket_uses_the_largest(self):
        ten = collection.unit_points(self.con, "Chaos - Death Guard", "Plague Marines", 10)
        many = collection.unit_points(self.con, "Chaos - Death Guard", "Plague Marines", 40)
        self.assertEqual(ten, many)

    def test_an_unknown_unit_has_no_points(self):
        self.assertIsNone(
            collection.unit_points(self.con, "Chaos - Death Guard", "Squat Warriors", 5))

    def tearDown(self):
        self.con.close()


if __name__ == "__main__":
    unittest.main()
