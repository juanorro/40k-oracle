"""Tests for dice expressions and roll probabilities."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import dice  # noqa: E402


class Expected(unittest.TestCase):
    def test_flat_values(self):
        self.assertEqual(dice.expected("4"), 4.0)

    def test_single_die(self):
        self.assertEqual(dice.expected("D6"), 3.5)
        self.assertEqual(dice.expected("D3"), 2.0)

    def test_multiple_dice_and_modifiers(self):
        self.assertEqual(dice.expected("2D6"), 7.0)
        self.assertEqual(dice.expected("D6+1"), 4.5)
        self.assertEqual(dice.expected("2D6+1"), 8.0)

    def test_lowercase_is_accepted(self):
        # The source is inconsistent: 'd6' occurs alongside 'D6'.
        self.assertEqual(dice.expected("d6+2"), 5.5)

    def test_unknown_values_fall_back(self):
        # '*' means "set by a rule the data does not carry".
        self.assertEqual(dice.expected("*"), 0.0)
        self.assertEqual(dice.expected(""), 0.0)
        self.assertEqual(dice.expected(None, default=1.0), 1.0)


class ExpectedCapped(unittest.TestCase):
    """Damage does not carry between models, so it is capped per model."""

    def test_capping_a_die_is_not_capping_its_average(self):
        # E[min(D6,3)] = (1+2+3+3+3+3)/6 = 2.5, not min(3.5,3) = 3.
        self.assertAlmostEqual(dice.expected_capped("D6", 3), 2.5)

    def test_flat_damage_caps_directly(self):
        self.assertEqual(dice.expected_capped("5", 2), 2)

    def test_cap_above_the_maximum_changes_nothing(self):
        self.assertAlmostEqual(dice.expected_capped("D6", 10), 3.5)

    def test_two_dice(self):
        # Over the 36 outcomes of 2D6: 2->2, 3->3 twice, 4->4 three times and
        # 4 for the remaining 30. (2 + 6 + 12 + 120) / 36.
        self.assertAlmostEqual(dice.expected_capped("2D6", 4), 140 / 36)


class Rolls(unittest.TestCase):
    def test_target_numbers(self):
        self.assertEqual(dice.target_number("3+"), 3)
        self.assertEqual(dice.target_number("4"), 4)
        self.assertIsNone(dice.target_number("N/A"))

    def test_plain_probability(self):
        self.assertAlmostEqual(dice.success(3), 4 / 6)

    def test_modifiers_are_capped_at_one(self):
        self.assertAlmostEqual(dice.success(4, 3), dice.success(4, 1))

    def test_a_two_up_cannot_be_improved(self):
        self.assertAlmostEqual(dice.success(2, 1), 5 / 6)

    def test_a_six_up_cannot_be_worsened_past_six(self):
        self.assertAlmostEqual(dice.success(6, -1), 1 / 6)

    def test_rerolling_failures(self):
        self.assertAlmostEqual(dice.reroll_failures(0.5), 0.75)


class WoundChart(unittest.TestCase):
    def test_against_toughness_four(self):
        self.assertEqual([dice.wound_target(s, 4) for s in (8, 5, 4, 3, 2)],
                         [2, 3, 4, 5, 6])

    def test_half_toughness_or_less_wounds_on_six(self):
        self.assertEqual(dice.wound_target(4, 8), 6)
        self.assertEqual(dice.wound_target(4, 7), 5)


if __name__ == "__main__":
    unittest.main()
