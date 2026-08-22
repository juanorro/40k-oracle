"""Tests for name normalisation and faction resolution."""
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import query  # noqa: E402
from names import name_keys, norm  # noqa: E402


class Norm(unittest.TestCase):
    def test_ignores_case_spacing_and_punctuation(self):
        self.assertEqual(norm("Death Lord’S Chosen"), "deathlordschosen")
        self.assertEqual(norm("Myphitic Blight-hauler"), "myphiticblighthauler")

    def test_empty_and_none(self):
        self.assertEqual(norm(None), "")
        self.assertEqual(norm("   "), "")


class NameKeys(unittest.TestCase):
    def test_singular_gets_a_plural(self):
        self.assertIn("myphiticblighthaulers", name_keys("Myphitic Blight-hauler"))

    def test_plural_gets_a_singular(self):
        self.assertIn("plaguemarine", name_keys("Plague Marines"))


class ResolveFaction(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.execute("create table faction_aliases (alias text, alias_norm text, "
                         "faction text, is_primary int)")
        rows = [("Death Guard", "Chaos - Death Guard", 1),
                ("Grey Knights", "Imperium - Grey Knights", 1),
                ("Chaos Knights", "Chaos - Chaos Knights Library", 1),
                ("Adeptus Custodes", "Imperium - Adeptus Custodes", 1),
                ("Chaos - Death Guard", "Chaos - Death Guard", 0)]
        self.con.executemany(
            "insert into faction_aliases values (?,?,?,?)",
            [(alias, norm(alias), faction, primary) for alias, faction, primary in rows])

    def test_exact_friendly_name(self):
        self.assertEqual(query.resolve_faction(self.con, "Death Guard")[0],
                         "Chaos - Death Guard")

    def test_case_and_spacing_do_not_matter(self):
        self.assertEqual(query.resolve_faction(self.con, "  deathguard ")[0],
                         "Chaos - Death Guard")

    def test_full_catalogue_name_still_works(self):
        self.assertEqual(query.resolve_faction(self.con, "Chaos - Death Guard")[0],
                         "Chaos - Death Guard")

    def test_unique_partial_match_resolves(self):
        self.assertEqual(query.resolve_faction(self.con, "custodes")[0],
                         "Imperium - Adeptus Custodes")

    def test_ambiguous_partial_returns_candidates(self):
        # 'knights' matches two different factions, so it must not guess.
        faction, candidates = query.resolve_faction(self.con, "knights")
        self.assertIsNone(faction)
        self.assertEqual(candidates,
                         ["Chaos - Chaos Knights Library", "Imperium - Grey Knights"])

    def test_a_substring_matching_one_faction_twice_still_resolves(self):
        # 'Death Guard' and 'Chaos - Death Guard' are aliases of one faction.
        self.assertEqual(query.resolve_faction(self.con, "guard")[0],
                         "Chaos - Death Guard")

    def test_unknown_returns_nothing(self):
        self.assertEqual(query.resolve_faction(self.con, "squats"), (None, []))

    def test_empty_input(self):
        self.assertEqual(query.resolve_faction(self.con, "")[0], None)

    def tearDown(self):
        self.con.close()


if __name__ == "__main__":
    unittest.main()
