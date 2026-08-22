"""Tests for the damage model, checked against hand arithmetic."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import combat  # noqa: E402

TARGET = {"t": 4, "sv": 3, "invuln": None, "w": 2, "keywords": ["Infantry"]}


def weapon(**overrides):
    """One attack, hits on 3+, S4, no AP, 1 damage."""
    return {"attacks": "1", "skill": "3+", "strength": "4", "ap": "0",
            "damage": "1", "keywords": "", **overrides}


class Baseline(unittest.TestCase):
    def test_hit_wound_save(self):
        # 3+ to hit (4/6), S4 vs T4 wounds on 4+ (3/6), Sv3+ fails 2/6.
        self.assertAlmostEqual(combat.expected_damage(weapon(), TARGET),
                               (4 / 6) * (3 / 6) * (2 / 6))

    def test_armour_penetration_worsens_the_save(self):
        self.assertAlmostEqual(combat.expected_damage(weapon(ap="-2"), TARGET),
                               (4 / 6) * (3 / 6) * (4 / 6))

    def test_invulnerable_save_is_used_when_better(self):
        target = dict(TARGET, invuln=4)
        self.assertAlmostEqual(combat.expected_damage(weapon(ap="-2"), target),
                               (4 / 6) * (3 / 6) * (3 / 6))

    def test_no_save_is_possible_past_six(self):
        self.assertAlmostEqual(combat.expected_damage(weapon(ap="-4"), TARGET),
                               (4 / 6) * (3 / 6))

    def test_star_strength_yields_nothing(self):
        self.assertEqual(combat.expected_damage(weapon(strength="*"), TARGET), 0.0)


class Abilities(unittest.TestCase):
    def test_torrent_always_hits(self):
        self.assertAlmostEqual(
            combat.expected_damage(weapon(keywords="Torrent"), TARGET),
            (3 / 6) * (2 / 6))

    def test_devastating_wounds_bypass_saves(self):
        expected = (4 / 6) * ((3 / 6 - 1 / 6) * (2 / 6) + 1 / 6)
        self.assertAlmostEqual(
            combat.expected_damage(weapon(keywords="Devastating Wounds"), TARGET),
            expected)

    def test_anti_keyword_lowers_the_critical_threshold(self):
        expected = (4 / 6) * ((3 / 6 - 3 / 6) * (2 / 6) + 3 / 6)
        self.assertAlmostEqual(
            combat.expected_damage(
                weapon(keywords="Anti-Infantry 4+, Devastating Wounds"), TARGET),
            expected)

    def test_anti_keyword_ignored_when_the_target_lacks_it(self):
        plain = combat.expected_damage(weapon(keywords="Devastating Wounds"), TARGET)
        with_anti = combat.expected_damage(
            weapon(keywords="Anti-Vehicle 2+, Devastating Wounds"), TARGET)
        self.assertAlmostEqual(plain, with_anti)

    def test_keyword_case_is_ignored(self):
        # 'Twin-linked' and 'Twin-Linked' both occur in the source.
        lower = combat.expected_damage(weapon(keywords="Twin-linked"), TARGET)
        upper = combat.expected_damage(weapon(keywords="Twin-Linked"), TARGET)
        self.assertAlmostEqual(lower, upper)
        self.assertGreater(lower, combat.expected_damage(weapon(), TARGET))

    def test_sustained_hits_add_hits(self):
        self.assertGreater(
            combat.expected_damage(weapon(keywords="Sustained Hits 1"), TARGET),
            combat.expected_damage(weapon(), TARGET))

    def test_blast_scales_with_target_size(self):
        small = combat.expected_damage(weapon(keywords="Blast"), TARGET,
                                       {"target_models": 5})
        large = combat.expected_damage(weapon(keywords="Blast"), TARGET,
                                       {"target_models": 20})
        self.assertGreater(large, small)

    def test_melta_only_applies_at_half_range(self):
        far = combat.expected_damage(weapon(damage="D6", keywords="Melta 2"), TARGET)
        near = combat.expected_damage(weapon(damage="D6", keywords="Melta 2"), TARGET,
                                      {"half_range": True})
        self.assertGreater(near, far)


class Damage(unittest.TestCase):
    def test_damage_is_capped_per_model(self):
        expected = (4 / 6) * (3 / 6) * (2 / 6) * ((1 + 2 + 2 + 2 + 2 + 2) / 6)
        self.assertAlmostEqual(combat.expected_damage(weapon(damage="D6"), TARGET),
                               expected)


class Keywords(unittest.TestCase):
    def test_parsing_values_and_flags(self):
        parsed = combat.parse_keywords("Sustained Hits 2, Torrent, Anti-Infantry 4+")
        self.assertEqual(parsed["sustained hits"], 2)
        self.assertEqual(parsed["anti-infantry"], 4)
        self.assertIs(parsed["torrent"], True)

    def test_empty(self):
        self.assertEqual(combat.parse_keywords(""), {})
        self.assertEqual(combat.parse_keywords(None), {})


if __name__ == "__main__":
    unittest.main()
