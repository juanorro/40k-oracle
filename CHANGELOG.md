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

### Notes

- Generated data is no longer tracked in git; see [NOTICE](NOTICE).
