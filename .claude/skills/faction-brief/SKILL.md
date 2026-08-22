---
name: faction-brief
description: Show what a faction can bring — detachments, enhancements, units by type, leader attachments. Use when the user asks what is in a faction, which detachments it has, what units fit a points budget, or wants an overview before building a list.
---

# Faction brief

Answer from `scripts/faction.py`, never from memory. Points and detachment
costs change with every balance dataslate; anything recalled is stale.

## Commands

```bash
python3 scripts/faction.py                                    # list every faction
python3 scripts/faction.py "death guard"                      # full dossier
python3 scripts/faction.py orks --keyword Battleline --max-points 120
python3 scripts/faction.py "death guard" --detachment "Virulent Vectorium"
python3 scripts/faction.py ultramarines --leaders
python3 scripts/faction.py "death guard" --allies --legends
```

Faction names are fuzzy: `death guard`, `Death Guard` and `custodes` all
resolve. If the script reports an ambiguity, show the candidates and ask.

If `index.db` is missing, say so and point at `scripts/sync-sources.sh` followed
by `scripts/build.py`. Do not answer the question anyway.

## Reading the output

- **DP** is the Detachment Points cost. The budget depends on battle size:
  2 at Incursion, 3 at Strike Force, 4 at Onslaught. Several detachments are
  allowed if they fit the budget.
- **`[unique: X]`** means two detachments sharing that tag cannot both be taken.
  The script already lists which ones clash — surface that, it is easy to miss.
- **Unit costs** read as `5:90 / 10:180`: model count and its price. Brackets are
  ceilings — six models pay the ten-model price if there is no bracket between.
- **`—`** for a cost means the unit is not in the official MFM, usually
  `[Legends]`. Say so rather than guessing a number.
- Allied catalogues and Legends units are hidden unless asked for.

## What to actually say

Lead with what shapes a list: how many DP the detachments cost against the
budget, which ones are mutually exclusive, and where the points sit. A raw dump
of every unit is rarely the answer to what was asked.
