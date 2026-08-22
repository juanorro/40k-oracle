#!/usr/bin/env python3
"""What an opponent can put in front of you, and what answers it.

  python3 scripts/analyse.py --threat "chaos space marines"
  python3 scripts/analyse.py --threat "chaos space marines" --attacker "death guard"

The threat profile is the spread of statlines a faction can field, not a guess
at one list. Weapons are then scored against every bracket, and ranked by their
WORST bracket: a list that has to answer anything cannot afford a weapon that
is excellent against one target and useless against the rest.
"""
import argparse
import collections
import sys

import combat
import query
from names import name_keys

# Toughness bands, in order of assignment: each unit lands in the first it
# matches. Taking the most common statlines instead would return six flavours
# of infantry and no vehicle, because infantry clusters and vehicles do not —
# which is the opposite of covering what an opponent can field.
BANDS = [
    ("chaff",         lambda t, sv, w: t <= 4 and sv >= 4),
    ("infantry",      lambda t, sv, w: t <= 5),
    ("elite",         lambda t, sv, w: t <= 7),
    ("monster",       lambda t, sv, w: t <= 10),
    ("heavy vehicle", lambda t, sv, w: True),
]


def statline(row):
    def number(value, default=None):
        text = (value or "").strip().rstrip("+")
        return int(text) if text.isdigit() else default
    return (number(row[0]), number(row[1]), number(row[2]), number(row[3]))


def threat_profiles(con, faction):
    """One representative statline per toughness band, covering the whole range.

    Within a band the most common statline represents it, and the unit count
    says how much of the roster sits there.
    """
    rows = con.execute(
        "select p.t, p.sv, p.w, p.invuln, u.name from units u "
        "join unit_profiles p on p.unit_id=u.id "
        "where u.faction=? and u.name not like '%[%'", (faction,)).fetchall()

    bands = {name: {"counter": collections.Counter(), "names": {}} for name, _ in BANDS}
    for row in rows:
        t, sv, w, invuln = statline(row[:4])
        if t is None or sv is None or w is None:
            continue
        band = next(name for name, matches in BANDS if matches(t, sv, w))
        key = (t, sv, w, invuln)
        bands[band]["counter"][key] += 1
        bands[band]["names"].setdefault(key, set()).add(row[4])

    profiles = []
    for name, _ in BANDS:
        counter = bands[name]["counter"]
        if not counter:
            continue
        key, _ = counter.most_common(1)[0]
        t, sv, w, invuln = key
        profiles.append({
            "band": name, "t": t, "sv": sv, "w": w, "invuln": invuln,
            "count": sum(counter.values()),
            "examples": sorted(bands[name]["names"][key])[:3],
            "keywords": ["Vehicle", "Monster"] if t >= 8 else ["Infantry"],
        })
    return profiles


def describe(profile):
    invuln = f" {profile['invuln']}++" if profile["invuln"] else ""
    return f"T{profile['t']} Sv{profile['sv']}+{invuln} W{profile['w']}"


def weapon_rows(con, scope):
    placeholders = ",".join("?" * len(scope))
    return con.execute(
        "select distinct w.name, w.kind, w.attacks, w.skill, w.strength, w.ap, "
        "w.damage, w.keywords from weapons w "
        "join unit_weapons uw on uw.weapon_id=w.id "
        "join units u on u.id=uw.unit_id "
        f"where u.faction in ({placeholders}) and u.name not like '%[%'", scope).fetchall()


def score_weapons(con, scope, profiles, kind=None, top=12):
    weapons = {}
    for name, weapon_kind, attacks, skill, strength, ap, damage, keywords in weapon_rows(con, scope):
        if kind and weapon_kind != kind:
            continue
        spec = {"attacks": attacks, "skill": skill, "strength": strength,
                "ap": ap, "damage": damage, "keywords": keywords}
        scores = [combat.expected_damage(spec, profile) for profile in profiles]
        if max(scores) <= 0:
            continue
        weapons[name] = scores
    ranked = sorted(weapons.items(), key=lambda item: min(item[1]), reverse=True)
    return ranked[:top], weapons


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--threat", required=True, help="the opposing faction")
    parser.add_argument("--attacker", help="your faction, to score its weapons")
    parser.add_argument("--melee", action="store_true", help="score melee instead of ranged")
    args = parser.parse_args()

    con = query.connect()
    defender, candidates = query.resolve_faction(con, args.threat)
    if defender is None:
        sys.exit(f"Unknown or ambiguous faction: '{args.threat}'. {', '.join(candidates[:6])}")

    profiles = threat_profiles(con, defender)
    print(f"THREAT PROFILE — {defender}")
    print("The statlines it can field, most common first.\n")
    for index, profile in enumerate(profiles, 1):
        print(f"  {index}. {profile['band']:<14} {describe(profile):<22} "
              f"{profile['count']:>3} units   e.g. {', '.join(profile['examples'])}")

    if not args.attacker:
        return
    attacker, candidates = query.resolve_faction(con, args.attacker)
    if attacker is None:
        sys.exit(f"Unknown or ambiguous faction: '{args.attacker}'. {', '.join(candidates[:6])}")

    scope = query.faction_scope(con, attacker)
    kind = "melee" if args.melee else "ranged"
    ranked, _ = score_weapons(con, [attacker], profiles, kind=kind)

    print(f"\n{kind.upper()} WEAPONS OF {attacker}, RANKED BY WORST BRACKET")
    print("Expected damage per weapon profile against each bracket above.\n")
    header = "  " + " ".join(f"{i:>6}" for i in range(1, len(profiles) + 1))
    print(f"  {'weapon':<34}{header}   worst")
    for name, scores in ranked:
        cells = " ".join(f"{value:6.2f}" for value in scores)
        print(f"  {name[:34]:<34}  {cells}  {min(scores):6.2f}")

    print("\nDamage ignores Feel No Pain, cover, stratagems, rerolls and army rules.")
    print("Use it to compare weapons with each other, not to predict a game.")


if __name__ == "__main__":
    main()
