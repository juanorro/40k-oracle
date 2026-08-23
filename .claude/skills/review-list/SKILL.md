---
name: review-list
description: Review an army list for gaps — what it can hurt, what it cannot, and what holds ground. Use when the user asks whether a list is good, what it is missing, how it fares against a faction, or wants a second opinion before a game.
---

# Review a list

```bash
python3 scripts/review.py lists/<name>.json
python3 scripts/review.py lists/<name>.json --vs "chaos space marines"
```

Use `--vs` whenever the opponent is known: measuring against what a faction can
actually field beats a generic spread.

## Reading it

The table is expected damage per threat band. A band under a third of the
strongest is flagged **thin**, and the tool names the units currently doing
that work — usually the more useful half of the answer, because it says whether
the gap is "nothing answers this" or "one unit does, and it dies early".

## What the numbers are not

Say this plainly rather than letting the table speak for itself:

- **Melee assumes contact.** Reaching the target is the hard part and is not
  modelled, so the melee column is a ceiling. Never compare it directly with
  ranged.
- **Damage is not quality.** A 390-point centrepiece bought for what it
  survives will score badly. That is the metric's blind spot, not the unit's.
- **Nothing here knows about missions, terrain, deployment or secondaries**,
  which is most of what decides a game.
- The model ignores Feel No Pain, cover, stratagems, rerolls and army rules.

## Turning it into advice

A flagged band is a question, not a verdict. Before suggesting swaps:

1. Check whether the thin band matters against that opponent — the unit count
   per band in `scripts/analyse.py --threat` says how much of their roster
   sits there. Being thin against a band they can barely field is fine.
2. Look at what already does the work. If one unit carries a whole band, the
   problem is fragility, not firepower.
3. Propose concrete swaps and **rebuild and revalidate the list** with
   `build-list` rather than describing changes in prose.

Report objective control and wound count too. A list that answers everything
and holds nothing loses.
