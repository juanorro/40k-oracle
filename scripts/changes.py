#!/usr/bin/env python3
"""Report what changed after re-syncing the sources, and what it broke.

  python3 scripts/changes.py --snapshot   before rebuilding
  python3 scripts/build.py
  python3 scripts/changes.py              after: diff, then revalidate lists/

Games Workshop ships balance dataslates. The question that actually matters is
not "what changed" but "which of my lists is now illegal".
"""
import argparse
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import query

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / ".snapshot.db"


def costs(con):
    return {(faction, unit, copies, models): points for faction, unit, copies, models, points
            in con.execute("select faction, unit, copies_from, models, points from mfm_points")}


def detachment_points(con):
    return {(faction, name): dp for faction, name, dp
            in con.execute("select faction, name, detachment_points from detachments")}


def report_diff():
    if not SNAPSHOT.exists():
        sys.exit("No snapshot to compare against. Run with --snapshot before rebuilding.")

    old, new = sqlite3.connect(SNAPSHOT), query.connect()
    old_version = old.execute("select version, updated from mfm_meta").fetchone()
    new_version = new.execute("select version, updated from mfm_meta").fetchone()
    if old_version != new_version:
        print(f"MFM {old_version[0]} ({old_version[1]})  ->  "
              f"{new_version[0]} ({new_version[1]})")
    else:
        print(f"MFM unchanged: v{new_version[0]} ({new_version[1]})")

    before, after = costs(old), costs(new)
    changed = [(k, before[k], after[k]) for k in before.keys() & after.keys()
               if before[k] != after[k]]
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())

    if changed:
        print(f"\nPOINTS CHANGED ({len(changed)})")
        for (faction, unit, copies, models), was, now in sorted(changed):
            copy_note = "" if copies == 1 else f", copy {copies}+"
            arrow = "▲" if now > was else "▼"
            print(f"  {arrow} {unit} ({models} models{copy_note}): {was} -> {now}"
                  f"   [{faction.split(' - ')[-1]}]")
    for label, rows in (("NEW ENTRIES", added), ("ENTRIES REMOVED", removed)):
        if rows:
            print(f"\n{label} ({len(rows)})")
            for faction, unit, copies, models in rows[:20]:
                print(f"  {unit} ({models} models)   [{faction.split(' - ')[-1]}]")
            if len(rows) > 20:
                print(f"  ... and {len(rows) - 20} more")

    before_dp, after_dp = detachment_points(old), detachment_points(new)
    dp_changed = [(k, before_dp[k], after_dp[k]) for k in before_dp.keys() & after_dp.keys()
                  if before_dp[k] != after_dp[k]]
    if dp_changed:
        print(f"\nDETACHMENT POINTS CHANGED ({len(dp_changed)})")
        for (faction, name), was, now in sorted(dp_changed):
            print(f"  {name}: {was} -> {now} DP   [{faction.split(' - ')[-1]}]")

    if not (changed or added or removed or dp_changed):
        print("\nNo data changes.")
    old.close()
    new.close()


def revalidate():
    lists = sorted((ROOT / "lists").glob("*.json"))
    if not lists:
        return 0
    print(f"\nREVALIDATING {len(lists)} list(s)")
    broken = 0
    for path in lists:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate.py"), str(path)],
            capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ok      {path.name}")
        else:
            broken += 1
            print(f"  BROKEN  {path.name}")
            for line in result.stdout.splitlines():
                if "ERROR" in line:
                    print(f"          {line.split('ERROR', 1)[1].strip()}")
    return broken


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--snapshot", action="store_true",
                        help="save the current index.db to compare against later")
    args = parser.parse_args()

    if args.snapshot:
        if not query.DB.exists():
            sys.exit("index.db missing. Run python3 scripts/build.py first.")
        shutil.copy(query.DB, SNAPSHOT)
        print(f"Snapshot saved to {SNAPSHOT.name}. Re-sync and rebuild, then run "
              f"this again without --snapshot.")
        return

    report_diff()
    broken = revalidate()
    sys.exit(1 if broken else 0)


if __name__ == "__main__":
    main()
