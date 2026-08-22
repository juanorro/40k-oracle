"""Tests for the list validation logic.

The pure-logic tests always run. The end-to-end ones need index.db, so they
skip on a fresh clone until scripts/build.py has been run.
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import validate  # noqa: E402


class SelectBracket(unittest.TestCase):
    """MFM brackets are ceilings, not floors."""

    BRACKETS = [(5, 90), (7, 125), (10, 180)]

    def test_exact_bracket(self):
        self.assertEqual(validate.select_bracket(self.BRACKETS, 5), (90, False))

    def test_between_brackets_pays_the_one_above(self):
        self.assertEqual(validate.select_bracket(self.BRACKETS, 6), (125, False))

    def test_top_bracket(self):
        self.assertEqual(validate.select_bracket(self.BRACKETS, 10), (180, False))

    def test_above_the_maximum_is_flagged(self):
        self.assertEqual(validate.select_bracket(self.BRACKETS, 12), (180, True))

    def test_no_brackets(self):
        self.assertEqual(validate.select_bracket([], 5), (None, False))


class NameKeys(unittest.TestCase):
    def test_covers_singular_and_plural(self):
        keys = validate.name_keys("Myphitic Blight-hauler")
        self.assertIn("myphiticblighthaulers", keys)
        keys = validate.name_keys("Plague Marines")
        self.assertIn("plaguemarine", keys)


@unittest.skipUnless((ROOT / "index.db").exists(), "run scripts/build.py first")
class EndToEnd(unittest.TestCase):
    def run_validator(self, path):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate.py"), str(path)],
            capture_output=True, text=True)

    def test_the_example_list_is_legal(self):
        result = self.run_validator(ROOT / "lists" / "example-death-guard.json")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("List is legal", result.stdout)

    def variant(self, **changes):
        import json
        import tempfile
        army = json.loads((ROOT / "lists" / "example-death-guard.json").read_text())
        army.update(changes)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(army, fh)
            path = Path(fh.name)
        try:
            return self.run_validator(path)
        finally:
            path.unlink()

    def test_detachment_budget_is_enforced(self):
        # The same list at Incursion: 3 DP of detachments against a budget of 2.
        result = self.variant(battle_size="Incursion")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Detachments:", result.stdout)

    def test_points_limit_is_enforced(self):
        import json
        army = json.loads((ROOT / "lists" / "example-death-guard.json").read_text())
        bulk = army["units"] + [{"name": "Mortarion"}] * 3
        result = self.variant(battle_size="Incursion", units=bulk)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Points:", result.stdout)


if __name__ == "__main__":
    unittest.main()
