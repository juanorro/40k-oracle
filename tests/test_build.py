"""Regression tests for the catalogue extraction logic.

Each test here corresponds to a bug that shipped once: flattened condition
trees, ignored `repeats` blocks, and profiles hidden below the parent entry.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build  # noqa: E402

PTS = "51b2-306e-1021-d207"
DP = "82ae-1066-5107-6ae0"
ENH = "f759-1bc4-cb3a-f0d2"


def cond(kind, value, child):
    return {"type": kind, "value": value, "field": "selections", "childId": child}


GAME_SYSTEM = {
    "sharedSelectionEntries": [{
        "name": "Battle Size",
        "selectionEntryGroups": [{"selectionEntries": [
            {"id": "inc", "name": "1. Incursion (1000 Point limit)"},
            {"id": "sf", "name": "2. Strike Force (2000 Point limit)"},
            {"id": "ons", "name": "3. Onslaught (3000 Point limit)"},
        ]}],
    }],
    "forceEntries": [{
        "constraints": [
            {"id": "c_dp", "type": "max", "field": DP, "value": 2},
            {"id": "c_pts", "type": "max", "field": PTS, "value": 0},
            {"id": "c_enh", "type": "max", "field": ENH, "value": 2},
        ],
        "modifiers": [
            # Strike Force OR (Incursion AND something else). Flattening this
            # tree wrongly gave Incursion 3 detachment points.
            {"type": "set", "field": "c_dp", "value": 3, "conditionGroups": [{
                "type": "or",
                "conditions": [cond("equalTo", 1, "sf")],
                "conditionGroups": [{"type": "and", "conditions": [
                    cond("equalTo", 1, "inc"), cond("atLeast", 1, "other")]}],
            }]},
            {"type": "set", "field": "c_dp", "value": 4,
             "conditions": [cond("equalTo", 1, "ons")]},
            {"type": "set", "field": "c_pts", "value": 1000,
             "conditions": [cond("atLeast", 1, "inc")]},
            {"type": "set", "field": "c_pts", "value": 2000,
             "conditions": [cond("atLeast", 1, "sf")]},
            {"type": "set", "field": "c_pts", "value": 3000,
             "conditions": [cond("atLeast", 1, "ons")]},
            # "+1 per Points limit option chosen". Nothing chooses it, so it
            # must never apply — it once produced limits of 2001 and 3001.
            {"type": "increment", "field": "c_pts", "value": 1,
             "repeats": [{"value": 1, "repeats": 1, "field": "selections",
                          "childId": "points-limit"}]},
            {"type": "set", "field": "c_enh", "value": 4,
             "conditions": [cond("equalTo", 0, "inc")]},
        ],
    }],
}


class BattleSizes(unittest.TestCase):
    def setUp(self):
        self.sizes = {s["name"]: s for s in build.battle_sizes(GAME_SYSTEM)}

    def test_points_limits(self):
        self.assertEqual(self.sizes["Incursion"]["points"], 1000)
        self.assertEqual(self.sizes["Strike Force"]["points"], 2000)
        self.assertEqual(self.sizes["Onslaught"]["points"], 3000)

    def test_nested_or_group_does_not_leak_to_incursion(self):
        self.assertEqual(self.sizes["Incursion"]["detachment_points"], 2)
        self.assertEqual(self.sizes["Strike Force"]["detachment_points"], 3)
        self.assertEqual(self.sizes["Onslaught"]["detachment_points"], 4)

    def test_negated_condition_applies_to_the_others(self):
        self.assertEqual(self.sizes["Incursion"]["enhancements"], 2)
        self.assertEqual(self.sizes["Strike Force"]["enhancements"], 4)


class Conditions(unittest.TestCase):
    def test_or_group_needs_only_one_branch(self):
        node = {"conditionGroups": [{"type": "or", "conditions": [
            cond("equalTo", 1, "a"), cond("equalTo", 1, "b")]}]}
        self.assertTrue(build.conditions_hold(node, "a"))
        self.assertFalse(build.conditions_hold(node, "c"))

    def test_and_group_needs_every_branch(self):
        node = {"conditionGroups": [{"type": "and", "conditions": [
            cond("equalTo", 1, "a"), cond("equalTo", 1, "b")]}]}
        self.assertFalse(build.conditions_hold(node, "a"))

    def test_conditions_on_other_fields_are_neutral(self):
        node = {"conditions": [{"type": "equalTo", "value": 3, "field": "forces"}]}
        self.assertTrue(build.conditions_hold(node, "a"))

    def test_no_conditions_always_holds(self):
        self.assertTrue(build.conditions_hold({}, "a"))


class Repeats(unittest.TestCase):
    def test_without_repeats_applies_once(self):
        self.assertEqual(build.repeat_count({}, "a"), 1)

    def test_repeats_counting_something_unselected_never_applies(self):
        mod = {"repeats": [{"value": 1, "childId": "other"}]}
        self.assertEqual(build.repeat_count(mod, "a"), 0)

    def test_repeats_counting_the_selection_applies(self):
        mod = {"repeats": [{"value": 1, "childId": "a"}]}
        self.assertEqual(build.repeat_count(mod, "a"), 1)


class PointsTiers(unittest.TestCase):
    def test_tiers_from_set_modifiers(self):
        entry = {
            "costs": [{"name": "pts", "typeId": PTS, "value": 90}],
            "modifiers": [
                {"type": "set", "field": PTS, "value": 125,
                 "conditions": [{"type": "atLeast", "value": 6, "childId": "model"}]},
                {"type": "set", "field": PTS, "value": 180,
                 "conditions": [{"type": "atLeast", "value": 8, "childId": "model"}]},
            ],
        }
        self.assertEqual(build.points_tiers(entry, PTS),
                         [{"min_models": 1, "pts": 90},
                          {"min_models": 6, "pts": 125},
                          {"min_models": 8, "pts": 180}])

    def test_cost_declared_on_the_child_model(self):
        entry = {"selectionEntries": [
            {"type": "model", "costs": [{"name": "pts", "typeId": PTS, "value": 100}]}]}
        self.assertEqual(build.points_tiers(entry, PTS), [{"min_models": 1, "pts": 100}])

    def test_no_cost_anywhere(self):
        self.assertEqual(build.points_tiers({}, PTS), [])


class Profiles(unittest.TestCase):
    def setUp(self):
        build.SHARED_PROFILES.clear()

    def _profile(self, pid, name):
        return {"id": pid, "name": name, "typeName": "Unit",
                "characteristics": [{"name": "T", "$text": "6"}]}

    def test_profile_on_the_entry(self):
        entry = {"profiles": [self._profile("p1", "Marine")]}
        self.assertEqual(build.unit_profiles(entry), [{"name": "Marine", "T": "6"}])

    def test_profile_on_the_child_model(self):
        entry = {"selectionEntries": [{"profiles": [self._profile("p1", "Hauler")]}]}
        self.assertEqual(build.unit_profiles(entry), [{"name": "Hauler", "T": "6"}])

    def test_profile_referenced_by_info_link(self):
        build.SHARED_PROFILES["p9"] = self._profile("p9", "Corsair")
        entry = {"selectionEntries": [{"infoLinks": [
            {"type": "profile", "targetId": "p9"}]}]}
        self.assertEqual(build.unit_profiles(entry), [{"name": "Corsair", "T": "6"}])

    def test_the_same_profile_is_not_counted_twice(self):
        build.SHARED_PROFILES["p9"] = self._profile("p9", "Corsair")
        link = {"infoLinks": [{"type": "profile", "targetId": "p9"}]}
        entry = {"selectionEntries": [link, dict(link)]}
        self.assertEqual(len(build.unit_profiles(entry)), 1)


class ArmyCap(unittest.TestCase):
    def test_max_in_force(self):
        entry = {"constraints": [
            {"type": "max", "field": "selections", "scope": "force", "value": 6}]}
        self.assertEqual(build.army_cap(entry), 6)

    def test_parent_scoped_constraints_are_not_army_caps(self):
        entry = {"constraints": [
            {"type": "max", "field": "selections", "scope": "parent", "value": 2}]}
        self.assertIsNone(build.army_cap(entry))


if __name__ == "__main__":
    unittest.main()
