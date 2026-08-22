---
name: sync-data
description: Re-sync the 40k data sources, rebuild the database, and report what changed and which saved lists it broke. Use when a balance dataslate or new Munitorum Field Manual is out, when data looks stale, or when the user asks to update.
---

# Sync the data

Games Workshop publishes balance dataslates. The question worth answering is
not "what changed" but "which of my lists is now illegal".

## Procedure

Run these in order. Do not skip the snapshot — without it there is nothing to
diff against and the update becomes invisible.

```bash
python3 scripts/changes.py --snapshot
./scripts/sync-sources.sh
python3 scripts/build.py
python3 scripts/changes.py
```

The last command prints the MFM version change, every points movement with
direction, new and removed entries, detachment cost changes, and then
revalidates every list in `lists/`. It exits non-zero if any list broke.

Finally, confirm nothing regressed in the extraction itself:

```bash
python3 -m unittest discover -s tests
```

## What to report

Lead with impact, not volume:

1. **Lists that broke**, and by how much. This is what the user cares about.
2. **Points changes affecting units they actually field** — cross-reference the
   diff against `lists/`.
3. The MFM version bump and a count of everything else.

A hundred point changes across factions nobody plays is one line. One unit in
their list going up 15 points is the headline.

## If the build fails after syncing

The upstream schema changed. Do not patch around it blindly: find what shape the
source now has, fix the extraction, and add a regression test. `CONTRIBUTING.md`
lists the parts of the BattleScribe schema that have already caused bugs.
