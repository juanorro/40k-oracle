# 40k-oracle

Structured, queryable data for **Warhammer 40,000 11th edition** — built to be
read by an AI agent, and to check that an army list is legal.

*[Léeme en español](README.es.md)*

No server, no Docker, no API. A build script, a SQLite file and some JSON.

## What it is

A pipeline that turns community catalogues and the official Munitorum Field
Manual into a dataset you can query exactly:

- **1,518 units** with characteristics, keywords and weapon profiles
- **2,972 official point costs**, including starting-strength brackets and
  Requisition Thresholds
- **395 detachments** with Detachment Points, Force Disposition and Unique tags
- **1,440 enhancements**, each linked to the detachment that unlocks it
- **2,137 Leader/Support attachments** — which character may join which unit
- A list validator that enforces all of the above

## What it is not

- **Not a rules reference.** No rules text is extracted or stored. For abilities
  and stratagems only the name is kept, as a pointer to the official source.
- **Not a GUI army builder.** Use [New Recruit](https://www.newrecruit.eu/) for
  that. This is for querying, analysing and validating.
- **Not affiliated with Games Workshop.** See [NOTICE](NOTICE).

## Quick start

```bash
pip install -r requirements.txt
./scripts/sync-sources.sh     # downloads ~75 MB of third-party sources
python3 scripts/build.py      # builds data/ and index.db in about a second
```

Nothing is committed to this repository except code: the dataset is built on
your machine and stays there.

## Querying

```bash
sqlite3 index.db "
  select u.name, p.points
  from units u join mfm_points p on p.unit_norm = lower(replace(u.name,' ',''))
  where u.faction like '%Death Guard%' order by p.points;"
```

Main tables:

| Table | Holds |
|---|---|
| `units` | identity, faction, single-model flag, army-wide maximum |
| `unit_profiles` | M, T, Sv, W, Ld, OC, invulnerable save |
| `mfm_points` | **official costs**, by model count and copy index |
| `weapons`, `unit_weapons` | weapon profiles and who carries them |
| `unit_keywords`, `unit_abilities` | keywords, ability names |
| `battle_sizes` | points, detachment and enhancement limits |
| `detachments`, `enhancements` | build options and what unlocks them |
| `leaders` | Leader/Support attachments |
| `catalogue_links` | which catalogues a faction inherits units from |

Full schema and interpretation rules: [CLAUDE.md](CLAUDE.md).

## Exploring a faction

```bash
python3 scripts/faction.py                       # list every faction
python3 scripts/faction.py "death guard"         # detachments, enhancements, units
python3 scripts/faction.py orks --keyword Battleline --max-points 120
```

Faction names are fuzzy: `death guard`, `Death Guard` and `custodes` all
resolve to their catalogue.

## Validating a list

```bash
python3 scripts/validate.py lists/example-death-guard.json
```

```json
{
  "faction": "Chaos - Death Guard",
  "battle_size": "Strike Force",
  "detachments": ["Virulent Vectorium"],
  "units": [
    { "name": "Typhus" },
    { "name": "Lord of Poxes", "enhancement": "Revolting Regeneration" },
    { "name": "Plague Marines", "models": 10 }
  ]
}
```

It checks the points limit (with Requisition Thresholds), the Detachment Points
budget, conflicting Unique tags, the enhancement cap and whether each
enhancement belongs to a chosen detachment and sits on a Character, the
per-unit maximum, the minimum of one Character, and whether leaders may join
the units they are attached to.

Every check comes from the catalogue data. None are hand-written rules.

## Keeping up with dataslates

```bash
python3 scripts/changes.py --snapshot
./scripts/sync-sources.sh && python3 scripts/build.py
python3 scripts/changes.py
```

Prints every points movement, detachment cost change and MFM version bump, then
revalidates every list in `lists/` and tells you which ones broke.

## Skills

`.claude/skills/` ships three skills for agents working in this repository:
`faction-brief`, `build-list` and `sync-data`. They encode the procedures above
and one standing rule: never write a points value that was not read from the
database.

## Why the Munitorum Field Manual is authoritative

Points come from the official MFM, not from BSData. Of 890 costs compared, **119
disagreed** — many by exactly double, because BSData lacks the larger
squad-size brackets:

```
Terminator Squad      10 models:  BSData=160   MFM=320
Deathwing Terminators 10 models:  BSData=165   MFM=330
Broadside Battlesuits  2 models:  BSData=75    MFM=150
```

A validator using BSData points passes lists that are well under strength. When
a unit is missing from the MFM, BSData is used **and the validator says so**.

## Sources

- [BSData/wh40k-11e](https://github.com/BSData/wh40k-11e) — community catalogues:
  units, profiles, weapons, wargear options, build constraints.
- [BSData/wh40k-11e-mfm](https://github.com/BSData/wh40k-11e-mfm) — mirror of the
  official [Munitorum Field Manual](https://mfm.warhammer-community.com/en).

Neither is endorsed by Games Workshop.

## Coverage and known gaps

- The MFM covers **95%** of normal-play units. The rest fall back to BSData with
  a warning. `[Legends]` and `[Crucible]` units are absent from the MFM by design.
- 8 units have no characteristic line (0.5%).
- Stratagems and detachment rules are not extracted — they are rules text.

## For AI agents

[CLAUDE.md](CLAUDE.md) is the contract: schema, interpretation rules, and one
standing instruction — never quote points or characteristics from memory, always
query the database. They change with every balance dataslate.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The one hard rule: no rules text.

## Licence

Code under the [MIT licence](LICENSE). The game data is not covered by it and is
not distributed here — read the [NOTICE](NOTICE).
