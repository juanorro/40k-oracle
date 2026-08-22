"""Shared read helpers over index.db."""
import sqlite3
from pathlib import Path

from names import norm

DB = Path(__file__).resolve().parent.parent / "index.db"


def connect():
    if not DB.exists():
        raise SystemExit("index.db missing. Run python3 scripts/build.py first.")
    return sqlite3.connect(DB)


def resolve_faction(con, text):
    """Turn whatever the user typed into a catalogue name.

    Catalogues are named the BSData way ('Chaos - Death Guard'); people type
    'death guard'. Returns (faction, candidates): faction is None when nothing
    matches or several do, and candidates explains which.
    """
    key = norm(text)
    if not key:
        return None, []
    row = con.execute(
        "select faction from faction_aliases where alias_norm=?", (key,)).fetchone()
    if row:
        return row[0], []
    matches = [r[0] for r in con.execute(
        "select distinct faction from faction_aliases where alias_norm like ?",
        (f"%{key}%",))]
    if len(matches) == 1:
        return matches[0], []
    return None, sorted(matches)


def faction_scope(con, faction):
    """The faction plus the catalogues it inherits units from.

    A chapter such as Ultramarines holds few units of its own and takes the
    rest from the Space Marines catalogue.
    """
    inherited = [r[0] for r in con.execute(
        "select inherits_from from catalogue_links where faction=?", (faction,))]
    return [faction, *inherited]


def faction_names(con):
    """Friendly names, for listing what is available."""
    return [r[0] for r in con.execute(
        "select distinct alias from faction_aliases where is_primary=1 order by alias")]
