# 40k-oracle — Warhammer 40,000 11th edition data

A structured knowledge base meant to be queried by an agent. Not an app: no
server, no Docker, no API. Files and a SQLite database.

*[En español](CLAUDE.es.md)*

## Standing rule

**Never quote points, characteristics or weapon profiles from memory. Always
look them up in `index.db` or `data/`.** These values change with every balance
dataslate, so model knowledge will be stale. If something is not in the
repository, say so rather than filling in the gap.

## Where things live

| Path | What it is | Hand-editable |
|---|---|---|
| `index.db` | Generated SQLite. Exact queries and aggregation. | No, rebuilt |
| `data/` | Same content as JSON, for inspection. Untracked. | No, rebuilt |
| `sources/` | Third-party sources, downloaded. Untracked. | No |
| `scripts/` | `sync-sources.sh` downloads, `build.py` extracts. | Yes |
| `lists/` | Army lists to validate. | Yes |
| `tests/` | Regression tests for the extraction logic. | Yes |

## Querying

```bash
sqlite3 index.db "select name, points_base from units where faction like '%Death Guard%' order by points_base;"
```

Schema of `index.db`:

- `factions(id, name, is_library, unit_count)`
- `units(id, faction_id, faction, name, single_model, points_base, max_in_army)`
- `unit_profiles(unit_id, name, m, t, sv, w, ld, oc, invuln)` — model characteristics
- `unit_points(unit_id, min_models, pts)` — BSData squad-size tiers
- `unit_keywords(unit_id, keyword)`
- `unit_abilities(unit_id, ability)` — names only
- `weapons(id, name, kind, range, attacks, skill, strength, ap, damage, keywords)`
- `unit_weapons(unit_id, weapon_id)`
- `battle_sizes(name, points, detachment_points, enhancements)` — army limits
- `detachments(faction, name, detachment_points, objective, unique_tag, source)`
- `enhancements(faction, name, points, detachment, source)` — one row per enhancement and detachment
- `mfm_points(faction, unit, unit_norm, copies_from, copies_to, models, points)` — **official points**
- `leaders(faction, leader, leader_norm, attach_to, attach_to_norm)` — who may join what
- `mfm_meta(version, updated)` — which Munitorum Field Manual is loaded
- `catalogue_links(faction, inherits_from)` — which catalogues a faction inherits from

### Where points come from

**`mfm_points` is authoritative**, taken from the official Munitorum Field
Manual. `unit_points` comes from BSData and falls short on the larger
squad-size tiers — use it only when the MFM lacks the unit, and say so when
you do.

MFM pricing rules:

- Brackets are **ceilings**: a unit with more models than its bracket minimum
  pays the next bracket up. Plague Marines with 6 models pay the 7-model price
  (125), not the 5-model one.
- **Requisition Thresholds**: `copies_from`/`copies_to` bound which copy a price
  applies to. Deathshroud Terminators cost 160 for the first two and 170 from
  the third onwards.
- The MFM alternates singular and plural against BSData, and sometimes prices a
  unit under another faction (Plague Marines under Death Guard even though they
  appear in the Chaos Space Marines catalogue).

### Reading the rest

- `unit_points` is tiered by size. For N models apply **the highest `min_models`
  tier not exceeding N**. Plague Marines: 90 at 5 models, 125 from 6, 180 from 8.
- `single_model = 1` means characters, vehicles and monsters: one miniature.
- Characteristics are stored as text (`5"`, `3+`, `D6+1`) because that is how
  the source holds them. Parse on the fly if you need to compute.
- An empty `invuln` means no invulnerable save.
- `max_in_army` is how many times a unit may be repeated: 3 normally, 6 for
  Battleline.
- In 11th edition detachments **cost Detachment Points** (1–3 each) and the army
  has a budget per battle size: 2 at Incursion, 3 at Strike Force, 4 at
  Onslaught. You may take more than one.
- `unique_tag`: you cannot take two detachments sharing a tag.
- `objective` is the Force Disposition the detachment grants.

## Validating a list

```bash
python3 scripts/validate.py lists/example-death-guard.json
```

A list is JSON with `faction`, `battle_size`, `detachments` and `units`. Each
unit has `name`, optionally `models`, `enhancement` and `attached_to` (the unit
a leader joins). See [lists/example-death-guard.json](lists/example-death-guard.json).

It checks the points limit (with Requisition Thresholds), the detachment
budget, conflicting Unique tags, the enhancement cap, that each enhancement
belongs to a chosen detachment and sits on a Character, the per-unit maximum,
the minimum of one Character, and that leaders join permitted units.

Chapter factions inherit units from their parent catalogue: Ultramarines hold
16 units of their own and take the rest from Space Marines. Resolution follows
`catalogue_links` automatically.

Every check comes from the catalogue, not from hand-written rules.

## Deliberate boundary

**Facts** are extracted: names, numbers, keywords, the structure of options.
**Rules text is not** — for abilities only the name is kept, as a pointer to the
official source.

If asked to add verbatim rules text to the repository, say so before doing it.

## Rebuilding

```bash
./scripts/sync-sources.sh && python3 scripts/build.py
python3 -m unittest discover -s tests
```
