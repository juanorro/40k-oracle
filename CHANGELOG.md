# Changelog

All notable changes to this project. Format based on
[Keep a Changelog](https://keepachangelog.com).

## [Unreleased]

### Added

- Extraction of BSData 11th edition catalogues into JSON and SQLite: units,
  model profiles, weapon profiles, keywords and ability names.
- Munitorum Field Manual as the authoritative source of points, including
  starting-strength brackets and Requisition Thresholds.
- Detachments with Detachment Points cost, Force Disposition and Unique tags;
  enhancements linked to the detachment that unlocks them.
- Leader/Support attachments: which character may join which unit.
- Catalogue inheritance, so chapter factions resolve units from their parent.
- `scripts/validate.py`: points limit, detachment budget, Unique tag conflicts,
  enhancement cap and ownership, per-unit maximum, minimum one Character, and
  leader attachment legality.
- Regression test suite covering the condition tree, `repeats` blocks, points
  brackets and faction matching.

- Faction aliases: `death guard` and `custodes` resolve to their catalogue, so
  BSData strings are no longer required anywhere.
- `scripts/faction.py`: faction dossier — detachments with DP and Unique clashes,
  enhancements, units by type with costs, leader attachments; filterable.
- `scripts/changes.py`: snapshot and diff across a dataslate, then revalidate
  every saved list.
- Skills for agents: `faction-brief`, `build-list`, `sync-data`.

- `scripts/dice.py` and `scripts/combat.py`: dice expressions and an expected
  damage model covering Torrent, Twin-linked, Sustained Hits, Lethal Hits,
  Devastating Wounds, Anti-X, Melta, Rapid Fire, Blast, Heavy and Lance, with
  damage capped per model.
- `scripts/analyse.py`: threat profile of a faction by toughness band, and
  weapons ranked by their worst bracket.

### Notes

- Generated data is no longer tracked in git; see [NOTICE](NOTICE).
