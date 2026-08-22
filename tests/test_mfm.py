"""Tests for reading the official Munitorum Field Manual."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import mfm  # noqa: E402


class ParseRange(unittest.TestCase):
    def test_open_ended(self):
        self.assertEqual(mfm.parse_range("[1,)"), (1, None))

    def test_closed(self):
        self.assertEqual(mfm.parse_range("[1,2]"), (1, 2))

    def test_third_copy_onwards(self):
        self.assertEqual(mfm.parse_range("[3,)"), (3, None))

    def test_missing_or_malformed_defaults_to_every_copy(self):
        self.assertEqual(mfm.parse_range(None), (1, None))
        self.assertEqual(mfm.parse_range("nonsense"), (1, None))


class MatchFaction(unittest.TestCase):
    def test_picks_the_catalogue_holding_the_units(self):
        # Both end in 'Tyranids'; picking the longer name chose the empty one.
        catalogues = {"Library - Tyranids": 15, "Xenos - Tyranids": 120}
        self.assertEqual(mfm.match_faction("Tyranids", catalogues), "Xenos - Tyranids")

    def test_alias_wins_over_suffix_match(self):
        catalogues = {"Aeldari - Aeldari Library": 200}
        self.assertEqual(mfm.match_faction("Drukhari", catalogues),
                         "Aeldari - Aeldari Library")

    def test_unknown_faction(self):
        self.assertIsNone(mfm.match_faction("Squats", {"Xenos - Orks": 90}))


class Norm(unittest.TestCase):
    def test_ignores_case_punctuation_and_spacing(self):
        self.assertEqual(mfm.norm("Death Lord’S Chosen"), mfm.norm("death lords chosen"))

    def test_handles_none(self):
        self.assertEqual(mfm.norm(None), "")


if __name__ == "__main__":
    unittest.main()
