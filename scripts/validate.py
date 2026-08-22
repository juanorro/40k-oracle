#!/usr/bin/env python3
"""Validate an army list against the data extracted into index.db.

Usage:  python3 scripts/validate.py lists/my-list.json

Points come from the official Munitorum Field Manual. If a unit is not in it,
BSData is used and a warning is emitted, because BSData falls short on the
larger squad-size tiers.
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "index.db"


def norm(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def name_keys(name):
    """The MFM alternates singular and plural against BSData."""
    base = norm(name)
    return (base, base + "s", base.rstrip("s"))


def select_bracket(rows, models):
    """Pick the cost bracket for `models`, given (models, points) rows sorted asc.

    MFM brackets are ceilings: a unit with more models than its bracket minimum
    pays the next bracket up. Returns (points, exceeded_max).
    """
    if not rows:
        return None, False
    for listed, points in rows:
        if models <= listed:
            return points, False
    return rows[-1][1], True


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def ok(self):
        return not self.errors


def faction_scope(con, faction):
    """The faction plus the catalogues it inherits units from.

    A chapter such as Ultramarines holds 16 units of its own and takes the rest
    from the Space Marines catalogue.
    """
    inherited = [r[0] for r in con.execute(
        "select inherits_from from catalogue_links where faction=?", (faction,))]
    return [faction, *inherited]


def mfm_cost(con, scope, unit_name, models, copy_index, report):
    """Official cost of copy number `copy_index` of the unit.

    Requisition Thresholds make extra copies more expensive, so the copy index
    selects which price band applies.
    """
    query = ("select models, points from mfm_points where faction=? and unit_norm in (?,?,?) "
             "and copies_from<=? and (copies_to is null or copies_to>=?) order by models")
    keys = name_keys(unit_name)

    rows = []
    for catalogue in scope:
        rows = con.execute(query, (catalogue, *keys, copy_index, copy_index)).fetchall()
        if rows:
            break

    if not rows:
        # Some units live in one catalogue and the MFM prices them under
        # another (Marine chapters, Tyranids, cult marines). Accept the price
        # if it comes from a single faction, and say which.
        elsewhere = con.execute(
            "select distinct faction from mfm_points where unit_norm in (?,?,?)", keys).fetchall()
        if len(elsewhere) != 1:
            return None
        source = elsewhere[0][0]
        rows = con.execute(query, (source, *keys, copy_index, copy_index)).fetchall()
        if rows:
            report.warn(f"'{unit_name}': the MFM prices it under {source}.")
    if not rows:
        return None

    points, exceeded = select_bracket(rows, models)
    if exceeded:
        report.warn(f"'{unit_name}': {models} models exceeds the MFM maximum "
                    f"({rows[-1][0]}); charged at that bracket.")
    return points


def bsdata_cost(con, unit_id, models):
    row = con.execute(
        "select pts from unit_points where unit_id=? and min_models<=? "
        "order by min_models desc limit 1", (unit_id, models)).fetchone()
    return row[0] if row else None


def resolve_unit(con, scope, name, report):
    for catalogue in scope:
        row = con.execute(
            "select id, name, max_in_army, single_model from units "
            "where faction=? and name=? collate nocase", (catalogue, name)).fetchone()
        if row:
            return (*row, catalogue)
    near = [r[0] for r in con.execute(
        "select name from units where faction in (%s) and name like ? limit 3"
        % ",".join("?" * len(scope)), (*scope, f"%{name}%"))]
    hint = f" Did you mean {', '.join(near)}?" if near else ""
    report.error(f"Unknown unit in {scope[0]}: '{name}'.{hint}")
    return None


def check_detachments(con, scope, names, report):
    chosen, spent, tags = [], 0, {}
    placeholders = ",".join("?" * len(scope))
    for name in names or []:
        row = con.execute(
            "select name, detachment_points, unique_tag from detachments "
            f"where faction in ({placeholders}) and name=? collate nocase",
            (*scope, name)).fetchone()
        if row is None:
            report.error(f"Unknown detachment in {scope[0]}: '{name}'.")
            continue
        det_name, dp, tag = row
        chosen.append(det_name)
        spent += dp or 0
        if tag:
            if tag in tags:
                report.error(f"'{det_name}' and '{tags[tag]}' share the Unique tag "
                             f"'{tag}'; you cannot take both.")
            tags[tag] = det_name
    if not chosen:
        report.error("The list declares no detachment.")
    return chosen, spent


def check_enhancement(con, scope, enh, unit_id, unit_name, chosen, report):
    placeholders = ",".join("?" * len(scope))
    rows = con.execute(
        "select points, detachment from enhancements "
        f"where faction in ({placeholders}) and name=? collate nocase",
        (*scope, enh)).fetchall()
    if not rows:
        report.error(f"Unknown enhancement in {scope[0]}: '{enh}'.")
        return 0
    if not con.execute("select 1 from unit_keywords where unit_id=? and keyword='Character'",
                       (unit_id,)).fetchone():
        report.error(f"'{enh}' is on '{unit_name}', which is not a Character.")

    owners = [d for _, d in rows if d]
    if owners and not {norm(o) for o in owners} & {norm(c) for c in chosen}:
        report.error(f"'{enh}' belongs to {', '.join(sorted(set(owners)))}, "
                     f"which is not in the list.")
    elif not owners:
        report.warn(f"'{enh}': the catalogue does not say which detachment it belongs to.")
    return rows[0][0] or 0


def check_leader(con, leader_name, target, in_list, report):
    """Check the leader may join that unit and that the unit is in the list."""
    allowed = [r[0] for r in con.execute(
        "select distinct attach_to from leaders where leader_norm in (?,?,?)",
        name_keys(leader_name))]
    if not allowed:
        report.warn(f"'{leader_name}': not listed as Leader/Support in the MFM, "
                    f"attachment not checked.")
    elif norm(target) not in {norm(a) for a in allowed}:
        report.error(f"'{leader_name}' cannot join '{target}'. "
                     f"It can join: {', '.join(sorted(allowed))}.")
    if norm(target) not in in_list:
        report.error(f"'{leader_name}' joins '{target}', which is not in the list.")


def validate(path):
    army = json.loads(Path(path).read_text())
    report = Report()
    con = sqlite3.connect(DB)

    size = con.execute(
        "select name, points, detachment_points, enhancements from battle_sizes where name=?",
        (army.get("battle_size"),)).fetchone()
    if size is None:
        options = [r[0] for r in con.execute("select name from battle_sizes")]
        report.error(f"Unknown battle size: '{army.get('battle_size')}'. "
                     f"Available: {', '.join(options)}.")
        return report, None
    size_name, pts_limit, dp_budget, enh_cap = size
    faction = army.get("faction")

    scope = faction_scope(con, faction)
    chosen, dp_spent = check_detachments(con, scope, army.get("detachments"), report)
    if dp_spent > dp_budget:
        report.error(f"Detachments: {dp_spent} DP against a budget of {dp_budget}.")

    in_list = {norm(u.get("name")) for u in army.get("units") or []}
    total, seen, characters, enh_used = 0, {}, 0, 0
    resolved = {}
    for item in army.get("units") or []:
        unit = resolve_unit(con, scope, item.get("name"), report)
        if unit is None:
            continue
        unit_id, unit_name, cap, single, catalogue = unit
        resolved[unit_name] = catalogue
        models = 1 if single else item.get("models", 1)

        if item.get("attached_to"):
            check_leader(con, unit_name, item["attached_to"], in_list, report)

        seen[unit_name] = seen.get(unit_name, 0) + 1
        cost = mfm_cost(con, scope, unit_name, models, seen[unit_name], report)
        if cost is None:
            cost = bsdata_cost(con, unit_id, models)
            if cost is None:
                report.warn(f"'{unit_name}': no points in any source, not counted.")
                cost = 0
            else:
                report.warn(f"'{unit_name}': not in the MFM, using BSData "
                            f"({cost} pts), which may be too low.")
        total += cost

        if con.execute("select 1 from unit_keywords where unit_id=? and keyword='Character'",
                       (unit_id,)).fetchone():
            characters += 1
        if item.get("enhancement"):
            enh_used += 1
            total += check_enhancement(con, scope, item["enhancement"],
                                       unit_id, unit_name, chosen, report)

    for name, count in seen.items():
        cap = con.execute("select max_in_army from units where faction=? and name=?",
                          (resolved[name], name)).fetchone()
        if cap and cap[0] and count > cap[0]:
            report.error(f"'{name}' appears {count} times; the maximum is {cap[0]}.")

    if characters == 0:
        # The system's 'Army Roster' force entry requires min 1 Character.
        report.error("The list has no Character; the rules require at least one.")
    if enh_used > enh_cap:
        report.error(f"Enhancements: {enh_used} used, the maximum at {size_name} is {enh_cap}.")
    if total > pts_limit:
        report.error(f"Points: {total} against a limit of {pts_limit} "
                     f"({total - pts_limit} over).")

    version = con.execute("select version, updated from mfm_meta").fetchone()
    con.close()
    return report, {"total": total, "limit": pts_limit, "dp": dp_spent,
                    "dp_budget": dp_budget, "enh": enh_used, "enh_cap": enh_cap,
                    "mfm": version}


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 scripts/validate.py <list.json>")
    if not DB.exists():
        sys.exit("index.db missing. Run python3 scripts/build.py first.")

    report, totals = validate(sys.argv[1])
    if totals:
        version, updated = totals["mfm"] or ("?", "?")
        print(f"Points {totals['total']}/{totals['limit']} | "
              f"Detachment {totals['dp']}/{totals['dp_budget']} | "
              f"Enhancements {totals['enh']}/{totals['enh_cap']}   "
              f"[MFM v{version}, {updated}]\n")
    for msg in report.warnings:
        print(f"  warning  {msg}")
    for msg in report.errors:
        print(f"  ERROR    {msg}")
    print("\nList is legal." if report.ok() else f"\n{len(report.errors)} problem(s).")
    sys.exit(0 if report.ok() else 1)


if __name__ == "__main__":
    main()
