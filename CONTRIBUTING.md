# Contributing

*[En español](CONTRIBUTING.es.md)*

## The one hard rule

**No rules text.** This project extracts facts — names, numeric
characteristics, points, keywords, the structure of build options. It does not
extract, store or redistribute the wording of rules, abilities, stratagems or
lore. For those, only the name is kept, as a pointer to the official
publication.

A pull request that ingests rules text will not be merged, however useful it
would be. See [NOTICE](NOTICE).

Likewise, do not commit anything under `data/`, `sources/` or `index.db`. They
are generated and deliberately untracked.

## Setting up

```bash
pip install -r requirements.txt
./scripts/sync-sources.sh
python3 scripts/build.py
python3 -m unittest discover -s tests
```

## How the pipeline fits together

```
sources/wh40k-11e       BSData catalogues (JSON, BattleScribe schema)
sources/wh40k-11e-mfm   Munitorum Field Manual mirror (YAML)
        │
        ├── scripts/mfm.py     reads the MFM: points, detachments, leaders
        └── scripts/build.py   reads BSData, merges the MFM over it
                │
                ├── data/*.json    inspectable output
                └── index.db       SQLite, what everything queries
        │
        ├── scripts/names.py    one normalisation, shared by everything
        ├── scripts/query.py    faction resolution and shared reads
        ├── scripts/faction.py  the faction dossier
        └── scripts/changes.py  diff after a dataslate, revalidate lists
```

`scripts/validate.py` only reads `index.db`. It never parses sources.

## Things that will bite you

The BattleScribe schema is more subtle than it looks, and each of these has
already caused a real bug:

- **Condition trees are boolean.** A modifier's conditions nest into `and`/`or`
  groups, sometimes several levels deep. Flatten them and you will apply limits
  to the wrong battle size.
- **`repeats` blocks gate modifiers.** An `increment` with a `repeats` block
  applies once per counted selection — zero times if nothing is selected.
- **A top-level `model` is a unit; a nested one is a squad member.** Getting
  this wrong loses every character and vehicle in the game.
- **Profiles hide in three places**: on the entry, on a child model, or behind
  an `infoLink` to a shared profile.
- **The MFM prices in ceilings.** A unit with more models than its bracket
  minimum pays the next bracket up, not the current one.

When you touch any of these, add a regression test. `tests/test_build.py`
documents the shape of each bug that got through before.

## Style

- Python 3.11+, standard library plus PyYAML. Resist adding dependencies.
- Comments in English, explaining *why* rather than *what*.
- Small functions, early returns, no clever one-liners in the parsing code.

## Reporting data problems

If a points value or profile looks wrong, check the source first — it is
usually upstream. Points issues belong in
[wh40k-11e-mfm](https://github.com/BSData/wh40k-11e-mfm); unit and wargear
issues in [wh40k-11e](https://github.com/BSData/wh40k-11e). Open an issue here
if the extraction is at fault.
