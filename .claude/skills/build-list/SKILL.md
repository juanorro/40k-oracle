---
name: build-list
description: Build a legal Warhammer 40,000 army list for a faction, battle size and detachment, then validate it. Use when the user asks to make, build or draft a list, an army, or a roster.
---

# Build a list

## Hard rules

1. **Never write a points value you did not read from the database.** This is
   the whole reason the project exists. Query it.
2. **The job is not done until `scripts/validate.py` exits clean.** A list you
   believe is legal but did not validate is not a delivered list.
3. If something cannot be made legal, say which constraint blocks it. Do not
   quietly drop a unit the user asked for.

## Procedure

**1. Establish faction, battle size and detachment.** Ask only what you cannot
infer. Then read the ground truth:

```bash
python3 scripts/faction.py "<faction>"
```

**2. Pick detachments within the DP budget.** Incursion 2, Strike Force 3,
Onslaught 4. Watch the `[unique: X]` tags — two detachments sharing one cannot
both be taken. Spending fewer DP than the budget is legal and sometimes right.

**3. Choose units.** Respect `max_in_army` (3 normally, 6 for Battleline) and
remember Requisition Thresholds: from the third copy a unit often costs more,
so the fourth Terminator squad is not the price of the first.

**4. Attach leaders.** `leaders` says which character may join which unit. Put
the target in `attached_to`; the character and the unit must both be in the list.

**5. Assign enhancements.** They must come from a chosen detachment and sit on a
Character. The cap is 2 at Incursion, 4 otherwise.

**6. Write and validate.**

```bash
python3 scripts/validate.py lists/<name>.json
```

Fix what it reports and run it again. Iterate until it exits 0.

## List format

```json
{
  "name": "Death Guard — Virulent Vectorium",
  "faction": "Death Guard",
  "battle_size": "Strike Force",
  "detachments": ["Virulent Vectorium"],
  "units": [
    { "name": "Typhus" },
    { "name": "Lord of Poxes", "enhancement": "Revolting Regeneration" },
    { "name": "Biologus Putrifier", "attached_to": "Plague Marines" },
    { "name": "Plague Marines", "models": 10 }
  ]
}
```

`models` is omitted for single-model units. Unit names must match the catalogue;
the validator suggests near matches when they do not.

## Interpreting failures

- *Unknown unit* — usually a naming variant. The suggestion in the message is
  normally right; check with `scripts/faction.py`.
- *X belongs to Y, which is not in the list* — the enhancement is from a
  detachment you did not take. Swap one or the other.
- *not in the MFM, using BSData* — a warning, not an error, but the cost may be
  too low. Tell the user rather than burying it.

## When you finish

Report the points total against the limit, the DP spent, and any warnings the
validator raised. If you left headroom, say how much — it is usually deliberate
on the user's part or an oversight on yours.
