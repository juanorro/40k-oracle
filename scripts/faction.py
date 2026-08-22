#!/usr/bin/env python3
"""Show what a faction can bring, before you start building a list.

Usage:
  python3 scripts/faction.py                          list every faction
  python3 scripts/faction.py "death guard"            full dossier
  python3 scripts/faction.py orks --keyword Battleline --max-points 100
  python3 scripts/faction.py "death guard" --detachment "Virulent Vectorium"
"""
import argparse
import sys

import query
from names import name_keys

GROUPS = ["Epic Hero", "Character", "Battleline", "Infantry", "Mounted",
          "Vehicle", "Monster", "Dedicated Transport", "Fortification"]


def unit_cost(con, scope, name):
    """Cost brackets for the first copy: '5:90 / 10:180', or a bare number."""
    keys = name_keys(name)
    for catalogue in scope:
        rows = con.execute(
            "select models, points from mfm_points where faction=? and unit_norm in (?,?,?) "
            "and copies_from=1 order by models", (catalogue, *keys)).fetchall()
        if rows:
            if len(rows) == 1 and rows[0][0] == 1:
                return str(rows[0][1])
            return " / ".join(f"{m}:{p}" for m, p in rows)
    return "—"


def show_detachments(con, faction):
    rows = con.execute(
        "select name, detachment_points, objective, unique_tag from detachments "
        "where faction=? order by detachment_points, name", (faction,)).fetchall()
    if not rows:
        return
    print("\nDETACHMENTS")
    for name, dp, objective, tag in rows:
        tag = f"  [unique: {tag}]" if tag else ""
        print(f"  {dp} DP  {name:<34} {objective or '':<16}{tag}")

    clashes = {}
    for name, _, _, tag in rows:
        if tag:
            clashes.setdefault(tag, []).append(name)
    for tag, names in clashes.items():
        if len(names) > 1:
            print(f"       incompatible ({tag}): {', '.join(names)}")


def show_enhancements(con, faction, only=None):
    sql = ("select detachment, name, points from enhancements where faction=? "
           "and detachment is not null")
    args = [faction]
    if only:
        sql += " and detachment=? collate nocase"
        args.append(only)
    rows = con.execute(sql + " order by detachment, name", args).fetchall()
    if not rows:
        return
    print("\nENHANCEMENTS")
    current = None
    for detachment, name, points in rows:
        if detachment != current:
            print(f"  {detachment}")
            current = detachment
        print(f"      {points or 0:>3} pts  {name}")


def show_units(con, faction, scope, keyword=None, max_points=None, legends=False):
    """List the faction's units by type.

    `scope` decides whether allied catalogues are included: a faction inherits
    from several (Daemons, Knights, Titans) and they otherwise drown out its
    own units.
    """
    wanted = [keyword] if keyword else GROUPS
    seen = set()
    for group in wanted:
        rows = con.execute(
            "select distinct u.name, u.faction from units u "
            "join unit_keywords k on k.unit_id=u.id "
            f"where u.faction in ({','.join('?' * len(scope))}) and k.keyword=? "
            "order by u.name", (*scope, group)).fetchall()
        listed = []
        for name, catalogue in rows:
            if name in seen:
                continue
            if not legends and ("[Legends]" in name or "[Crucible]" in name):
                continue
            cost = unit_cost(con, scope, name)
            if max_points is not None:
                first = cost.split(" / ")[0].split(":")[-1]
                if not first.isdigit() or int(first) > max_points:
                    continue
            seen.add(name)
            borrowed = "" if catalogue == faction else f"   ({catalogue.split(' - ')[-1]})"
            listed.append(f"      {cost:>14}  {name}{borrowed}")
        if listed:
            print(f"\n{group.upper()}  ({len(listed)})")
            print("\n".join(listed))


def show_leaders(con, scope):
    rows = con.execute(
        f"select leader, group_concat(attach_to, ', ') from leaders "
        f"where faction in ({','.join('?' * len(scope))}) "
        "group by leader order by leader", scope).fetchall()
    if not rows:
        return
    print(f"\nLEADERS  ({len(rows)})")
    for leader, targets in rows:
        print(f"      {leader}  ->  {targets}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("faction", nargs="?", help="faction name, e.g. 'death guard'")
    parser.add_argument("--keyword", help="show only units with this keyword")
    parser.add_argument("--max-points", type=int, help="hide units above this cost")
    parser.add_argument("--detachment", help="show only this detachment's enhancements")
    parser.add_argument("--leaders", action="store_true", help="include leader attachments")
    parser.add_argument("--allies", action="store_true",
                        help="include units from inherited catalogues")
    parser.add_argument("--legends", action="store_true",
                        help="include [Legends] and [Crucible] units")
    args = parser.parse_args()

    con = query.connect()

    if not args.faction:
        print("Factions:")
        for name in query.faction_names(con):
            print(f"  {name}")
        return

    faction, candidates = query.resolve_faction(con, args.faction)
    if faction is None:
        if candidates:
            sys.exit(f"'{args.faction}' is ambiguous: {', '.join(candidates[:8])}")
        sys.exit(f"Unknown faction: '{args.faction}'. Run without arguments to list them.")

    full_scope = query.faction_scope(con, faction)
    scope = full_scope if args.allies else [faction]
    print(f"{faction.upper()}")
    if len(full_scope) > 1:
        allied = ", ".join(c.split(" - ")[-1] for c in full_scope[1:])
        note = "included" if args.allies else "use --allies to include"
        print(f"  allied catalogues ({note}): {allied}")

    sizes = con.execute("select name, points, detachment_points, enhancements "
                        "from battle_sizes").fetchall()
    print("\nBATTLE SIZES")
    for name, points, dp, enh in sizes:
        print(f"  {name:<14} {points:>5} pts   {dp} DP   {enh} enhancements")

    # Filtering units means the reader is after units, not the whole dossier.
    filtering = bool(args.keyword or args.max_points)
    if not filtering or args.detachment:
        show_detachments(con, faction)
        show_enhancements(con, faction, args.detachment)
    show_units(con, faction, scope, args.keyword, args.max_points, args.legends)
    if args.leaders:
        show_leaders(con, full_scope)
    con.close()


if __name__ == "__main__":
    main()
