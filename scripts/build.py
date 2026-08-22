#!/usr/bin/env python3
"""Extrae datos estructurados de los catálogos BSData 11e a data/*.json e index.db.

Frontera deliberada: se extraen HECHOS (nombres, perfiles numéricos, puntos,
keywords, estructura de wargear). No se extrae el texto de las reglas: de las
habilidades se guarda solo el nombre, como referencia.
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sources" / "wh40k-11e"
DATA = ROOT / "data"
DB = ROOT / "index.db"

WEAPON_TYPES = {"Ranged Weapons", "Melee Weapons"}
CHILD_KEYS = ("sharedSelectionEntries", "selectionEntries",
              "sharedSelectionEntryGroups", "selectionEntryGroups")

# Perfiles declarados una vez y referenciados por infoLink desde muchas
# entradas. Se rellena en main() con todos los catalogos.
SHARED_PROFILES = {}


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "sin-nombre"


def walk(node):
    """Recorre todas las entradas anidadas de un nodo."""
    for key in CHILD_KEYS:
        for entry in node.get(key) or []:
            yield entry
            yield from walk(entry)


def all_modifiers(entry):
    yield from entry.get("modifiers") or []
    for group in entry.get("modifierGroups") or []:
        yield from group.get("modifiers") or []


def points_tiers(entry, pts_type_id, depth=0):
    """Puntos base y por tamaño de unidad (los modifiers 'set' sobre el coste)."""
    base = next((c.get("value") for c in entry.get("costs") or []
                 if c.get("name") == "pts"), None)
    if base is None:
        # Algunas unidades declaran el coste en el modelo hijo, no en el padre.
        if depth < 2:
            for child in entry.get("selectionEntries") or []:
                if child.get("type") == "model":
                    tiers = points_tiers(child, pts_type_id, depth + 1)
                    if tiers:
                        return tiers
        return []
    tiers = {1: base}
    for mod in all_modifiers(entry):
        if mod.get("type") != "set" or mod.get("field") != pts_type_id:
            continue
        for cond in mod.get("conditions") or []:
            if cond.get("type") == "atLeast" and cond.get("childId") == "model":
                tiers[cond.get("value")] = mod.get("value")
    return [{"min_models": k, "pts": v} for k, v in sorted(tiers.items())]


def characteristics(profile):
    return {c.get("name"): (c.get("$text") or "").strip()
            for c in profile.get("characteristics") or []}


def unit_profiles(entry, depth=0, seen=None):
    """Linea de caracteristicas de la unidad.

    Algunas unidades no la llevan en la entrada padre sino en el modelo hijo,
    Puede estar en la propia entrada, referenciada por infoLink a un perfil
    compartido, o colgando del modelo hijo. Se buscan las tres, sin seguir
    entryLinks para no arrastrar perfiles de otras unidades.
    """
    if seen is None:
        seen = set()
    found = []
    candidates = list(entry.get("profiles") or [])
    candidates += [SHARED_PROFILES[link["targetId"]]
                   for link in entry.get("infoLinks") or []
                   if link.get("type") == "profile" and link.get("targetId") in SHARED_PROFILES]
    for prof in candidates:
        if prof.get("typeName") != "Unit" or prof.get("id") in seen:
            continue
        seen.add(prof.get("id"))
        found.append({"name": prof.get("name"), **characteristics(prof)})
    if found or depth >= 3:
        return found
    for key in ("selectionEntries", "selectionEntryGroups"):
        for child in entry.get(key) or []:
            found.extend(unit_profiles(child, depth + 1, seen))
    return found


def collect_subtree(entry, id_map, seen=None, depth=0):
    """Entradas del subárbol de una unidad, resolviendo entryLinks."""
    if seen is None:
        seen = set()
    key = id(entry)
    if key in seen or depth > 8:
        return
    seen.add(key)
    yield entry
    for child in (e for k in CHILD_KEYS for e in entry.get(k) or []):
        yield from collect_subtree(child, id_map, seen, depth + 1)
    for link in entry.get("entryLinks") or []:
        target = id_map.get(link.get("targetId"))
        if target is not None:
            yield from collect_subtree(target, id_map, seen, depth + 1)


def weapons_of(entry, id_map):
    found = {}
    for node in collect_subtree(entry, id_map):
        for prof in node.get("profiles") or []:
            if prof.get("typeName") not in WEAPON_TYPES:
                continue
            ch = characteristics(prof)
            found[prof["id"]] = {
                "id": prof["id"],
                "name": prof.get("name"),
                "kind": "melee" if prof["typeName"] == "Melee Weapons" else "ranged",
                "range": ch.get("Range", ""),
                "attacks": ch.get("A", ""),
                "skill": ch.get("BS") or ch.get("WS") or ch.get("BS/WS", ""),
                "strength": ch.get("S", ""),
                "ap": ch.get("AP", ""),
                "damage": ch.get("D", ""),
                "keywords": ch.get("Keywords", ""),
            }
    return list(found.values())


def ability_names(entry, id_map):
    """Solo nombres. El texto de la regla se queda en la fuente."""
    names = []
    for node in collect_subtree(entry, id_map):
        for link in node.get("infoLinks") or []:
            if link.get("type") == "rule" and link.get("name"):
                names.append(link["name"])
    return sorted(set(names))


def keywords_of(entry):
    return sorted({link["name"] for link in entry.get("categoryLinks") or []
                   if link.get("name")})


def main():
    if not SRC.is_dir():
        sys.exit("No hay fuentes. Ejecuta primero scripts/sync-sources.sh")

    catalogues, roots = [], []
    for path in sorted(SRC.glob("*.json")):
        with path.open() as fh:
            doc = json.load(fh)
        # El fichero del sistema de juego aporta entradas compartidas para
        # resolver enlaces, pero no es una faccion.
        if "catalogue" in doc:
            catalogues.append(doc["catalogue"])
            roots.append(doc["catalogue"])
        elif "gameSystem" in doc:
            roots.append(doc["gameSystem"])

    for root in roots:
        for prof in root.get("sharedProfiles") or []:
            SHARED_PROFILES[prof["id"]] = prof

    id_map = {}
    for root in roots:
        for entry in walk(root):
            if entry.get("id"):
                id_map[entry["id"]] = entry

    pts_type_id = None
    for cat in catalogues:
        for entry in walk(cat):
            for cost in entry.get("costs") or []:
                if cost.get("name") == "pts":
                    pts_type_id = cost.get("typeId")
                    break
            if pts_type_id:
                break
        if pts_type_id:
            break

    DATA.mkdir(exist_ok=True)
    (DATA / "units").mkdir(exist_ok=True)
    for stale in (DATA / "units").glob("*.json"):
        stale.unlink()

    factions, all_units, all_weapons = [], [], {}

    for cat in catalogues:
        units = []
        # Solo entradas de nivel superior: un 'model' anidado es un miembro de
        # escuadra, mientras que uno de nivel superior es una unidad de un solo
        # modelo (personaje, vehiculo, monstruo).
        top_level = (cat.get("sharedSelectionEntries") or []) + (cat.get("selectionEntries") or [])
        for entry in top_level:
            if entry.get("type") not in ("unit", "model") or entry.get("hidden"):
                continue
            weapons = weapons_of(entry, id_map)
            for weapon in weapons:
                all_weapons[weapon["id"]] = weapon
            profiles = unit_profiles(entry)
            tiers = points_tiers(entry, pts_type_id)
            # Sin coste y sin linea de caracteristicas no es una unidad
            # seleccionable, sino un componente reutilizable de escuadra
            # (p.ej. "Wolf Scout", "Burna Boy") publicado en el nivel superior.
            if not profiles and not tiers:
                continue
            units.append({
                "id": entry["id"],
                "name": entry.get("name"),
                "faction_id": cat["id"],
                "faction": cat["name"],
                "single_model": entry.get("type") == "model",
                "points": tiers,
                "profiles": profiles,
                "keywords": keywords_of(entry),
                "abilities": ability_names(entry, id_map),
                "weapons": [w["id"] for w in weapons],
            })

        units.sort(key=lambda u: u["name"] or "")
        factions.append({
            "id": cat["id"],
            "name": cat["name"],
            "is_library": bool(cat.get("library")),
            "unit_count": len(units),
        })
        all_units.extend(units)
        if units:
            out = DATA / "units" / f"{slugify(cat['name'])}.json"
            out.write_text(json.dumps(units, indent=1, ensure_ascii=False) + "\n")

    factions.sort(key=lambda f: f["name"])
    (DATA / "factions.json").write_text(
        json.dumps(factions, indent=1, ensure_ascii=False) + "\n")
    (DATA / "weapons.json").write_text(
        json.dumps(sorted(all_weapons.values(), key=lambda w: w["name"] or ""),
                   indent=1, ensure_ascii=False) + "\n")

    build_db(factions, all_units, all_weapons)
    print(f"{len(factions)} catálogos | {len(all_units)} unidades | "
          f"{len(all_weapons)} perfiles de arma")
    print(f"data/ y {DB.name} regenerados")


def build_db(factions, units, weapons):
    DB.unlink(missing_ok=True)
    con = sqlite3.connect(DB)
    con.executescript("""
      create table factions (id text primary key, name text, is_library int, unit_count int);
      create table units (id text primary key, faction_id text, faction text, name text,
                          single_model int, points_base int);
      create table unit_profiles (unit_id text, name text, m text, t text, sv text,
                                  w text, ld text, oc text, invuln text);
      create table unit_points (unit_id text, min_models int, pts int);
      create table unit_keywords (unit_id text, keyword text);
      create table unit_abilities (unit_id text, ability text);
      create table weapons (id text primary key, name text, kind text, range text,
                            attacks text, skill text, strength text, ap text,
                            damage text, keywords text);
      create table unit_weapons (unit_id text, weapon_id text);
    """)
    con.executemany("insert into factions values (?,?,?,?)",
                    [(f["id"], f["name"], int(f["is_library"]), f["unit_count"]) for f in factions])
    con.executemany("insert or ignore into units values (?,?,?,?,?,?)",
                    [(u["id"], u["faction_id"], u["faction"], u["name"], int(u["single_model"]),
                      u["points"][0]["pts"] if u["points"] else None) for u in units])
    con.executemany("insert into unit_profiles values (?,?,?,?,?,?,?,?,?)",
                    [(u["id"], p.get("name"), p.get("M"), p.get("T"), p.get("Sv"),
                      p.get("W"), p.get("LD"), p.get("OC"), p.get("InSv"))
                     for u in units for p in u["profiles"]])
    con.executemany("insert into unit_points values (?,?,?)",
                    [(u["id"], t["min_models"], t["pts"]) for u in units for t in u["points"]])
    con.executemany("insert into unit_keywords values (?,?)",
                    [(u["id"], k) for u in units for k in u["keywords"]])
    con.executemany("insert into unit_abilities values (?,?)",
                    [(u["id"], a) for u in units for a in u["abilities"]])
    con.executemany("insert into weapons values (?,?,?,?,?,?,?,?,?,?)",
                    [(w["id"], w["name"], w["kind"], w["range"], w["attacks"], w["skill"],
                      w["strength"], w["ap"], w["damage"], w["keywords"])
                     for w in weapons.values()])
    con.executemany("insert into unit_weapons values (?,?)",
                    [(u["id"], wid) for u in units for wid in u["weapons"]])
    con.executescript("""
      create index units_faction_idx on units(faction_id);
      create index unit_keywords_idx on unit_keywords(keyword);
      create index unit_weapons_idx on unit_weapons(unit_id);
      create index weapons_name_idx on weapons(name);
    """)
    con.commit()
    con.close()


if __name__ == "__main__":
    main()
