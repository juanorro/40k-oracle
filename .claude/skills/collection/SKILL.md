---
name: collection
description: Track which miniatures the user owns and check what a list still needs them to buy. Use when they ask what they can field, what is missing for a list, what to buy next, or want to record models they own.
---

# Collection

```bash
python3 scripts/collection.py                          # what is owned
python3 scripts/collection.py --faction "death guard"
python3 scripts/collection.py --check lists/my-list.json
```

`collection/collection.json` is the user's own file and is not in git. If it is
missing, the example is shown instead and the tool says so — offer to create the
real one rather than editing the example.

## The format

```json
[
  { "faction": "Death Guard", "unit": "Plague Marines", "models": 14,
    "wargear": ["2x plasma gun"], "acquired": "2026-03-11" }
]
```

`faction` and `unit` must resolve against the catalogue; the tool reports what
it cannot recognise. `models` is how many miniatures, not how many units — 14
Plague Marines can be a squad of 10 and one of 5, or one of 14 if the datasheet
allows it. `wargear` and `acquired` are recorded for reference only and are not
checked against anything, so do not use them to claim a list is fieldable.

Paint status is deliberately not tracked.

## Checking a list

`--check` totals every model the list needs — including the same unit taken
twice — and reports the shortfall per unit. It exits non-zero when anything is
missing, so it can gate a build.

## Using it well

When building a list for someone who has told you what they own, check it
before presenting the list, and say plainly what they would have to buy. A
legal list they cannot field is not much use.

If they ask what to buy next, prefer what unlocks the most: a unit short by one
model, or a gap the `review-list` skill flagged as thin. Say which reason
applies rather than just naming a box.
