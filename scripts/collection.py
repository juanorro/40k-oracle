#!/usr/bin/env python3
"""What you own, and what a list still needs you to buy.

  python3 scripts/collection.py                        what is in the collection
  python3 scripts/collection.py --faction "death guard"
  python3 scripts/collection.py --check lists/my-list.json

The collection lives in collection/collection.json by default. Entries record
the unit and how many models of it you own; `wargear` and `acquired` are kept
for your own reference and are not checked against anything.
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import query
from names import norm

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "collection" / "collection.json"
EXAMPLE = ROOT / "collection" / "example-collection.json"


def load(path):
    if path.exists():
        return json.loads(path.read_text()), path
    if path == DEFAULT and EXAMPLE.exists():
        return json.loads(EXAMPLE.read_text()), EXAMPLE
    sys.exit(f"No collection at {path}. Copy {EXAMPLE.name} and edit it.")


def resolve(con, faction_text, unit_name):
    """Find the unit in its faction or any catalogue that faction inherits."""
    faction, candidates = query.resolve_faction(con, faction_text)
    if faction is None:
        return None, None, candidates
    for catalogue in query.faction_scope(con, faction):
        row = con.execute(
            "select id, name from units where faction=? and name=? collate nocase",
            (catalogue, unit_name)).fetchone()
        if row:
            return faction, row, []
    return faction, None, []


def unit_points(con, faction, unit_name, models):
    """Cheapest bracket covering `models`, mirroring how the MFM prices a unit."""
    keys = (norm(unit_name), norm(unit_name) + "s", norm(unit_name).rstrip("s"))
    rows = con.execute(
        "select models, points from mfm_points where faction=? and unit_norm in (?,?,?) "
        "and copies_from=1 order by models", (faction, *keys)).fetchall()
    for listed, points in rows:
        if models <= listed:
            return points
    return rows[-1][1] if rows else None


def owned_models(entries):
    """Total models per (faction, unit), since a unit may be listed twice."""
    totals = defaultdict(int)
    for entry in entries:
        totals[(entry.get("faction"), entry.get("unit"))] += entry.get("models", 0)
    return totals


def show(con, entries, faction_filter):
    wanted = None
    if faction_filter:
        wanted, candidates = query.resolve_faction(con, faction_filter)
        if wanted is None:
            sys.exit(f"Unknown faction: {faction_filter!r}. {', '.join(candidates[:5])}")

    by_faction = defaultdict(list)
    unknown = []
    for entry in entries:
        faction, row, candidates = resolve(con, entry.get("faction"), entry.get("unit"))
        if faction is None:
            unknown.append(f"{entry.get('faction')} (unknown faction)")
            continue
        if wanted and faction != wanted:
            continue
        if row is None:
            unknown.append(f"{entry.get('unit')} in {faction}")
            continue
        models = entry.get("models", 0)
        points = unit_points(con, faction, row[1], models)
        by_faction[faction].append((row[1], models, points, entry.get("wargear")))

    for faction, rows in sorted(by_faction.items()):
        total = sum(points or 0 for _, _, points, _ in rows)
        print(f"\n{faction}   ({len(rows)} entries, about {total} pts of models)")
        for name, models, points, wargear in sorted(rows):
            cost = f"{points:>4} pts" if points else "   — pts"
            extra = f"   [{', '.join(wargear)}]" if wargear else ""
            print(f"  {models:>3}x  {name:<34} {cost}{extra}")
    if unknown:
        print(f"\nNot recognised ({len(unknown)}): {'; '.join(unknown)}")


def check(con, entries, list_path):
    army = json.loads(Path(list_path).read_text())
    faction_text = army.get("faction")
    faction, candidates = query.resolve_faction(con, faction_text)
    if faction is None:
        sys.exit(f"Unknown faction: {faction_text!r}. {', '.join(candidates[:5])}")
    scope = query.faction_scope(con, faction)

    owned = defaultdict(int)
    for (entry_faction, unit), models in owned_models(entries).items():
        resolved, row, _ = resolve(con, entry_faction, unit)
        if row is not None:
            owned[norm(row[1])] += models

    needed = defaultdict(int)
    names = {}
    for item in army.get("units") or []:
        row = None
        for catalogue in scope:
            row = con.execute(
                "select id, name, single_model from units where faction=? and name=? "
                "collate nocase", (catalogue, item.get("name"))).fetchone()
            if row:
                break
        if row is None:
            print(f"  ?   {item.get('name')} — not in the catalogue")
            continue
        models = 1 if row[2] else item.get("models", 1)
        needed[norm(row[1])] += models
        names[norm(row[1])] = row[1]

    print(f"{army.get('name') or Path(list_path).stem}   vs your collection\n")
    missing = []
    for key, count in sorted(needed.items(), key=lambda item: names[item[0]]):
        have = owned.get(key, 0)
        if have >= count:
            print(f"  ok    {names[key]:<34} need {count}, have {have}")
        else:
            short = count - have
            missing.append((names[key], short))
            print(f"  SHORT {names[key]:<34} need {count}, have {have}   buy {short}")

    if missing:
        total = sum(short for _, short in missing)
        print(f"\n{total} models short across {len(missing)} unit(s).")
    else:
        print("\nYou own everything this list needs.")
    return 1 if missing else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", type=Path, default=DEFAULT, help="collection JSON")
    parser.add_argument("--faction", help="show only this faction")
    parser.add_argument("--check", help="a list to check against the collection")
    args = parser.parse_args()

    entries, used = load(args.file)
    con = query.connect()
    if used != args.file:
        print(f"(using {used.name}; create {DEFAULT.name} for your own)")

    if args.check:
        sys.exit(check(con, entries, args.check))
    show(con, entries, args.faction)


if __name__ == "__main__":
    main()
