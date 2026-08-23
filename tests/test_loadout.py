"""Regression tests for default loadout extraction.

Each case here is a shape that produced a wrong answer once: containers whose
real choices sit a level down, fixed wargear inside those containers, and
single-model units that are their own model.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build  # noqa: E402


def weapon(entry_id, name):
    return {"id": entry_id, "name": name, "type": "upgrade",
            "profiles": [{"id": f"p-{entry_id}", "name": name,
                          "typeName": "Ranged Weapons", "characteristics": []}]}


def link(link_id, target, minimum=None):
    node = {"id": link_id, "targetId": target, "type": "selectionEntry"}
    if minimum is not None:
        node["constraints"] = [{"type": "min", "field": "selections", "value": minimum}]
    return node


ID_MAP = {"w-bolt": weapon("w-bolt", "Boltgun"),
          "w-knife": weapon("w-knife", "Plague knives"),
          "w-plasma": weapon("w-plasma", "Plasma gun")}


def profiles(ids):
    return sorted(i.replace("p-w-", "") for i in ids)


class DirectWargear(unittest.TestCase):
    def test_a_linked_weapon_is_always_carried(self):
        model = {"entryLinks": [link("l1", "w-bolt")]}
        self.assertEqual(profiles(build.default_weapon_ids(model, ID_MAP)), ["bolt"])


class Containers(unittest.TestCase):
    def test_container_group_is_followed_to_its_sub_group_default(self):
        # A 'Wargear' group with no constraints and no default of its own is a
        # container: the real pick is one level down.
        model = {"selectionEntryGroups": [{
            "name": "Wargear",
            "selectionEntryGroups": [{
                "name": "Gun choice",
                "defaultSelectionEntryId": "l-bolt",
                "constraints": [{"type": "min", "field": "selections", "value": 1}],
                "entryLinks": [link("l-bolt", "w-bolt"), link("l-plasma", "w-plasma")],
            }],
        }]}
        self.assertEqual(profiles(build.default_weapon_ids(model, ID_MAP)), ["bolt"])

    def test_fixed_wargear_inside_a_container_is_taken(self):
        # Links with min 1 are equipment the model always has.
        model = {"selectionEntryGroups": [{
            "name": "Wargear",
            "entryLinks": [link("l1", "w-bolt", minimum=1),
                           link("l2", "w-knife", minimum=1)],
        }]}
        self.assertEqual(profiles(build.default_weapon_ids(model, ID_MAP)),
                         ["bolt", "knife"])

    def test_optional_links_inside_a_container_are_not_taken(self):
        model = {"selectionEntryGroups": [{
            "name": "Options",
            "entryLinks": [link("l1", "w-plasma")],
        }]}
        self.assertEqual(build.default_weapon_ids(model, ID_MAP), [])

    def test_a_group_contributes_only_its_default(self):
        model = {"selectionEntryGroups": [{
            "name": "Gun choice",
            "defaultSelectionEntryId": "l-bolt",
            "entryLinks": [link("l-bolt", "w-bolt"), link("l-plasma", "w-plasma")],
        }]}
        self.assertEqual(profiles(build.default_weapon_ids(model, ID_MAP)), ["bolt"])


class Loadout(unittest.TestCase):
    def test_a_single_model_unit_is_its_own_model(self):
        unit = {"name": "Typhus", "type": "model",
                "entryLinks": [link("l1", "w-bolt")]}
        rows = build.default_loadout(unit, ID_MAP)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["model"], rows[0]["count_min"]), ("Typhus", 1))

    def test_a_squad_takes_its_mandatory_model_and_the_group_default(self):
        unit = {
            "name": "Plague Marines", "type": "unit",
            "selectionEntries": [{
                "name": "Champion", "type": "model",
                "constraints": [{"type": "min", "field": "selections", "value": 1},
                                {"type": "max", "field": "selections", "value": 1}],
                "entryLinks": [link("l1", "w-bolt")],
            }],
            "selectionEntryGroups": [{
                "name": "Plague Marines",
                "defaultSelectionEntryId": "m-bolt",
                "constraints": [{"type": "min", "field": "selections", "value": 4},
                                {"type": "max", "field": "selections", "value": 9}],
                "selectionEntries": [
                    {"id": "m-bolt", "name": "Marine w/ boltgun", "type": "model",
                     "entryLinks": [link("l2", "w-bolt")]},
                    {"id": "m-plasma", "name": "Marine w/ plasma", "type": "model",
                     "entryLinks": [link("l3", "w-plasma")]},
                ],
            }],
        }
        rows = {row["model"]: row for row in build.default_loadout(unit, ID_MAP)}
        self.assertEqual(set(rows), {"Champion", "Marine w/ boltgun"})
        self.assertEqual(rows["Champion"]["count_min"], 1)
        self.assertEqual((rows["Marine w/ boltgun"]["count_min"],
                          rows["Marine w/ boltgun"]["count_max"]), (4, 9))

    def test_optional_models_are_not_in_the_default_loadout(self):
        unit = {"name": "Squad", "type": "unit", "selectionEntryGroups": [{
            "name": "Special weapons",
            "constraints": [{"type": "max", "field": "selections", "value": 2}],
            "selectionEntries": [{"id": "m1", "name": "Melta marine", "type": "model"}],
        }]}
        self.assertEqual(build.default_loadout(unit, ID_MAP), [])


if __name__ == "__main__":
    unittest.main()
