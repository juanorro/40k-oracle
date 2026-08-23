"""Tests for spreading a squad's models over its loadout entries."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import review  # noqa: E402

CHAMPION = {"model": "Champion", "count_min": 1, "count_max": 1}
TROOPS = {"model": "Marine", "count_min": 4, "count_max": 9}


class ScaleLoadout(unittest.TestCase):
    def spread(self, rows, models):
        return {row["model"]: count for row, count in review.scale_loadout(rows, models)}

    def test_a_full_squad_fills_the_flexible_entry(self):
        self.assertEqual(self.spread([CHAMPION, TROOPS], 10),
                         {"Champion": 1, "Marine": 9})

    def test_a_minimum_squad_takes_the_lower_bound(self):
        self.assertEqual(self.spread([CHAMPION, TROOPS], 5),
                         {"Champion": 1, "Marine": 4})

    def test_the_flexible_entry_never_exceeds_its_maximum(self):
        spread = self.spread([CHAMPION, TROOPS], 20)
        self.assertEqual(spread["Marine"], 9)

    def test_a_single_model_unit(self):
        self.assertEqual(self.spread([{"model": "Typhus", "count_min": 1,
                                       "count_max": 1}], 1), {"Typhus": 1})

    def test_all_entries_fixed_but_more_models_scales_the_first(self):
        # Some squads declare every model as a fixed entry; the extras have to
        # land somewhere rather than vanish from the count.
        rows = [{"model": "Nurgling swarm", "count_min": 3, "count_max": 3}]
        self.assertEqual(self.spread(rows, 6), {"Nurgling swarm": 6})

    def test_no_loadout_at_all(self):
        self.assertEqual(review.scale_loadout([], 5), [])


if __name__ == "__main__":
    unittest.main()
