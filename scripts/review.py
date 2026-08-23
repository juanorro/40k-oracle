#!/usr/bin/env python3
"""Review a list: what it can hurt, what it cannot, and what it holds ground with.

  python3 scripts/review.py lists/my-list.json
  python3 scripts/review.py lists/my-list.json --vs "chaos space marines"

Without `--vs` the list is measured against a generic spread of statlines.
With it, against what that faction can actually field.

Melee totals assume contact: getting there is the hard part and is not
modelled, so the melee column is a ceiling rather than an expectation.
"""
import argparse
import json
import sys
from pathlib import Path

import analyse
import combat
import query
from names import name_keys, norm

# Used when no opponent is named: the shape of most armies, roughly.
GENERIC = [
    {"band": "chaff", "t": 3, "sv": 6, "w": 1, "invuln": None, "keywords": ["Infantry"]},
    {"band": "infantry", "t": 4, "sv": 3, "w": 2, "invuln": None, "keywords": ["Infantry"]},
    {"band": "elite", "t": 6, "sv": 2, "w": 4, "invuln": 4, "keywords": ["Infantry"]},
    {"band": "monster", "t": 10, "sv": 3, "w": 10, "invuln": None, "keywords": ["Monster"]},
    {"band": "heavy vehicle", "t": 12, "sv": 2, "w": 16, "invuln": None, "keywords": ["Vehicle"]},
]

THIN = 0.35          # a band under this share of the best one is a hole


def scale_loadout(rows, models):
    """Spread a squad's models over its loadout entries.

    Fixed entries (a champion, min == max) take their count; whatever is left
    goes to the flexible entry, clamped to its own range.
    """
    fixed = [row for row in rows if row["count_min"] == row["count_max"]]
    flexible = [row for row in rows if row["count_min"] != row["count_max"]]
    used = sum(row["count_min"] for row in fixed)
    scaled = [(row, row["count_min"]) for row in fixed]
    remaining = max(0, models - used)
    for row in flexible:
        take = max(row["count_min"], min(row["count_max"], remaining))
        scaled.append((row, take))
        remaining -= take
    if not rows:
        return []
    if not flexible and used < models:      # every entry fixed: scale the first
        first, count = scaled[0]
        scaled[0] = (first, count + models - used)
    return scaled


def loadout_rows(con, unit_id):
    grouped = {}
    for model, count_min, count_max, name, kind, attacks, skill, strength, ap, damage, keywords in con.execute(
            "select l.model, l.count_min, l.count_max, w.name, w.kind, w.attacks, w.skill, "
            "w.strength, w.ap, w.damage, w.keywords from unit_loadout l "
            "join weapons w on w.id=l.weapon_id where l.unit_id=?", (unit_id,)):
        row = grouped.setdefault(model, {"model": model, "count_min": count_min,
                                         "count_max": count_max, "weapons": []})
        row["weapons"].append({"name": name, "kind": kind, "attacks": attacks,
                               "skill": skill, "strength": strength, "ap": ap,
                               "damage": damage, "keywords": keywords})
    return list(grouped.values())


def unit_totals(con, unit_id, models, profiles):
    """Ranged and melee damage per threat band, plus wounds and objective control."""
    rows = loadout_rows(con, unit_id)
    ranged = [0.0] * len(profiles)
    melee = [0.0] * len(profiles)
    for row, count in scale_loadout(rows, models):
        for weapon in row["weapons"]:
            for index, profile in enumerate(profiles):
                value = count * combat.expected_damage(weapon, profile)
                (melee if weapon["kind"] == "melee" else ranged)[index] += value

    stats = con.execute(
        "select name, w, oc from unit_profiles where unit_id=?", (unit_id,)).fetchall()
    wounds = objective = 0
    if stats:
        by_name = {norm(name): (w, oc) for name, w, oc in stats}
        counted = 0
        for row, count in scale_loadout(rows, models):
            match = by_name.get(norm(row["model"]))
            if match is None:
                continue
            wounds += count * int(match[0] or 0)
            objective += count * int(match[1] or 0)
            counted += count
        if counted < models:                # profiles named differently: fall back
            w, oc = stats[0][1], stats[0][2]
            wounds += (models - counted) * int(w or 0)
            objective += (models - counted) * int(oc or 0)
    return ranged, melee, wounds, objective, bool(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("list", help="path to the list JSON")
    parser.add_argument("--vs", help="opposing faction; omit for a generic spread")
    args = parser.parse_args()

    army = json.loads(Path(args.list).read_text())
    con = query.connect()

    faction, candidates = query.resolve_faction(con, army.get("faction"))
    if faction is None:
        sys.exit(f"Unknown faction: {army.get('faction')!r}. {', '.join(candidates[:5])}")
    scope = query.faction_scope(con, faction)

    if args.vs:
        opponent, candidates = query.resolve_faction(con, args.vs)
        if opponent is None:
            sys.exit(f"Unknown faction: {args.vs!r}. {', '.join(candidates[:5])}")
        profiles = analyse.threat_profiles(con, opponent)
        against = opponent
    else:
        profiles, against = GENERIC, "a generic spread"

    print(f"{army.get('name') or Path(args.list).stem}")
    print(f"  {faction}  ·  {army.get('battle_size')}  ·  measured against {against}\n")

    ranged = [0.0] * len(profiles)
    melee = [0.0] * len(profiles)
    wounds = objective = models_total = 0
    unscored = []
    contributions = []

    for item in army.get("units") or []:
        row = None
        for catalogue in scope:
            row = con.execute(
                "select id, name, single_model from units where faction=? and name=? "
                "collate nocase", (catalogue, item.get("name"))).fetchone()
            if row:
                break
        if row is None:
            unscored.append(f"{item.get('name')} (not found)")
            continue
        unit_id, name, single = row
        models = 1 if single else item.get("models", 1)
        models_total += models
        unit_ranged, unit_melee, unit_wounds, unit_oc, had_loadout = unit_totals(
            con, unit_id, models, profiles)
        if not had_loadout:
            unscored.append(f"{name} (no default loadout in the source)")
        ranged = [a + b for a, b in zip(ranged, unit_ranged)]
        melee = [a + b for a, b in zip(melee, unit_melee)]
        wounds += unit_wounds
        objective += unit_oc
        contributions.append((name, unit_ranged, unit_melee))

    print(f"  {models_total} models  ·  {wounds} wounds  ·  {objective} objective control\n")

    print(f"  {'threat band':<16}{'ranged':>9}{'melee':>9}{'total':>9}   share")
    totals = [r + m for r, m in zip(ranged, melee)]
    best = max(totals) or 1
    holes = []
    for index, profile in enumerate(profiles):
        share = totals[index] / best
        flag = "  ← thin" if share < THIN else ""
        if share < THIN:
            holes.append(profile["band"])
        print(f"  {profile['band']:<16}{ranged[index]:9.1f}{melee[index]:9.1f}"
              f"{totals[index]:9.1f}   {share:5.0%}{flag}")

    if holes:
        print(f"\n  Thin against: {', '.join(holes)}.")
        for band in holes:
            index = next(i for i, p in enumerate(profiles) if p["band"] == band)
            best_units = sorted(contributions,
                                key=lambda c: c[1][index] + c[2][index], reverse=True)[:3]
            named = ", ".join(f"{n} ({r[index] + m[index]:.1f})" for n, r, m in best_units)
            print(f"    most of what you have into {band}: {named}")
    else:
        print("\n  No band falls below a third of the strongest; the list is even.")

    if unscored:
        print(f"\n  Not scored ({len(unscored)}): {'; '.join(unscored)}")

    print("\n  Melee assumes the unit is in contact, so its column is a ceiling, not a")
    print("  forecast: reaching the target is the hard part and is not modelled. Ranged")
    print("  and melee are therefore not directly comparable with each other.")
    print("  Damage also ignores Feel No Pain, cover, stratagems, rerolls and army rules,")
    print("  and says nothing about deployment, missions or how a game is won.")


if __name__ == "__main__":
    main()
