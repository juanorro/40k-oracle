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

import mfm

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


def entries_with_parent(node):
    """Cada entrada anidada junto al contenedor directo que la declara."""
    for key in CHILD_KEYS:
        for child in node.get(key) or []:
            yield child, node
            yield from entries_with_parent(child)


def cost_named(entry, name):
    return next((c.get("value") for c in entry.get("costs") or []
                 if c.get("name") == name), None)


def condition_child_ids(node):
    """Condiciones de un modifier, incluidas las de grupos anidados."""
    for cond in node.get("conditions") or []:
        yield cond
    for group in node.get("conditionGroups") or []:
        yield from condition_child_ids(group)


def army_cap(entry):
    """Cuantas veces puede repetirse la unidad en el ejercito."""
    for con in entry.get("constraints") or []:
        if (con.get("type") == "max" and con.get("field") == "selections"
                and con.get("scope") in ("force", "roster")):
            return con.get("value")
    return None


def condition_holds(cond, chosen_id):
    """Evalua una condicion suponiendo que solo esta elegido `chosen_id`."""
    if cond.get("field") != "selections":
        return True          # no depende del tamano de partida
    count = 1 if cond.get("childId") == chosen_id else 0
    value = cond.get("value") or 0
    return {
        "equalTo": count == value,
        "notEqualTo": count != value,
        "atLeast": count >= value,
        "atMost": count <= value,
        "lessThan": count < value,
        "greaterThan": count > value,
    }.get(cond.get("type"), True)


def conditions_hold(node, chosen_id, operator="and"):
    """Evalua el arbol de condiciones respetando los and/or de cada grupo."""
    results = [condition_holds(c, chosen_id) for c in node.get("conditions") or []]
    results += [conditions_hold(g, chosen_id, g.get("type", "and"))
                for g in node.get("conditionGroups") or []]
    if not results:
        return True
    return all(results) if operator == "and" else any(results)


def repeat_count(modifier, chosen_id):
    """Veces que se aplica un modifier con bloque `repeats`.

    Suponiendo que solo esta elegido el tamano de partida, cualquier `repeats`
    que cuente otra cosa da cero y el modifier no llega a aplicarse.
    """
    repeats = modifier.get("repeats") or []
    if not repeats:
        return 1
    counts = []
    for rep in repeats:
        selected = 1 if rep.get("childId") == chosen_id else 0
        counts.append(selected // (rep.get("value") or 1))
    return min(counts)


def battle_sizes(gs):
    """Limites de puntos, destacamentos y realces segun el tamano de partida.

    El sistema declara un limite base en el 'Army Roster' y lo reescribe con
    modifiers condicionados al Battle Size. Las condiciones forman un arbol
    and/or que hay que evaluar entero: aplanarlo da limites equivocados.
    """
    entry = next((e for e in gs.get("sharedSelectionEntries") or []
                  if e.get("name") == "Battle Size"), None)
    if entry is None:
        return []
    options = {}
    for group in entry.get("selectionEntryGroups") or []:
        for opt in group.get("selectionEntries") or []:
            if "Point limit" in (opt.get("name") or ""):
                options[opt["id"]] = re.sub(r"^\d+\.\s*", "", opt["name"]).split(" (")[0]

    force = (gs.get("forceEntries") or [{}])[0]
    fields = {"51b2-306e-1021-d207": "points",
              "82ae-1066-5107-6ae0": "detachment_points",
              "f759-1bc4-cb3a-f0d2": "enhancements"}
    limits = {con["id"]: (fields[con["field"]], con.get("value"))
              for con in force.get("constraints") or []
              if con.get("field") in fields and con.get("type") == "max"}

    sizes = []
    for oid, name in options.items():
        values = {key: base for key, base in limits.values()}
        # En orden de documento, como los aplica BattleScribe.
        for mod in force.get("modifiers") or []:
            if mod.get("field") not in limits or not conditions_hold(mod, oid):
                continue
            times = repeat_count(mod, oid)
            if times < 1:
                continue
            key = limits[mod["field"]][0]
            if mod.get("type") == "set":
                values[key] = mod.get("value")
            elif mod.get("type") == "increment":
                values[key] += (mod.get("value") or 0) * times
            elif mod.get("type") == "decrement":
                values[key] -= (mod.get("value") or 0) * times
        sizes.append({"name": name, **values})
    return sizes


def merge_sources(bsdata_rows, mfm_rows, mfm_only_keys):
    """Fusiona por faccion + nombre normalizado. El MFM sobrescribe."""
    merged = {}
    for row in bsdata_rows:
        key = (row["faction"], mfm.norm(row["name"]))
        merged[key] = {**row, **{k: None for k in mfm_only_keys}, "source": "bsdata"}
    for row in mfm_rows:
        key = (row["faction"], mfm.norm(row["name"]))
        merged[key] = {**merged.get(key, {}), **row, "source": "mfm"}
    return sorted(merged.values(), key=lambda r: (r["faction"], r["name"] or ""))


def merge_enhancements(bsdata_rows, mfm_rows):
    """Una fila por realce y destacamento. El MFM manda en puntos y vinculo."""
    merged = {}
    for row in bsdata_rows:
        for det in row["detachments"] or [None]:
            merged[(row["faction"], mfm.norm(row["name"]), mfm.norm(det))] = {
                "faction": row["faction"], "name": row["name"],
                "points": row["points"], "detachment": det, "source": "bsdata"}
    for row in mfm_rows:
        merged[(row["faction"], mfm.norm(row["name"]), mfm.norm(row["detachment"]))] = {
            **row, "source": "mfm"}
    return sorted(merged.values(), key=lambda r: (r["faction"], r["name"] or ""))


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

    # Un catalogo de capitulo (Ultramarines) declara de que otros hereda
    # unidades. Sin esto, sus listas no resuelven.
    catalogue_by_id = {r["id"]: r["name"] for r in roots}
    links = []
    for cat in catalogues:
        for link in cat.get("catalogueLinks") or []:
            target = catalogue_by_id.get(link.get("targetId"))
            if target and target != cat["name"]:
                links.append({"faction": cat["name"], "inherits_from": target})

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
    all_detachments, all_enhancements = [], []
    detachment_names = {}

    # Un destacamento es lo que cuesta Detachment Points; un realce, lo que
    # cuesta Enhancements. Es el discriminador mas estable de la fuente.
    for cat in catalogues:
        for entry, _ in entries_with_parent(cat):
            if (cost_named(entry, "Detachment Points") or 0) >= 1:
                detachment_names[entry["id"]] = entry.get("name")
                all_detachments.append({
                    "id": entry["id"],
                    "name": entry.get("name"),
                    "faction": cat["name"],
                    "detachment_points": cost_named(entry, "Detachment Points"),
                })

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
                "max_in_army": army_cap(entry),
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

    # Los realces cuelgan de un grupo que se oculta salvo que este elegido su
    # destacamento; esas condiciones son el vinculo entre ambos.
    # Un mismo realce aparece bajo cada personaje que puede llevarlo, y cada
    # aparicion esta condicionada a un destacamento distinto, asi que hay que
    # acumular los vinculos de todas ellas en vez de quedarse con la primera.
    by_id = {}
    for cat in catalogues:
        for entry, parent in entries_with_parent(cat):
            if (cost_named(entry, "Enhancements") or 0) < 1:
                continue
            record = by_id.setdefault(entry["id"], {
                "id": entry["id"],
                "name": entry.get("name"),
                "faction": cat["name"],
                "points": cost_named(entry, "pts"),
                "detachments": set(),
            })
            # El gating puede estar en el grupo contenedor o en el propio realce.
            for mod in (entry.get("modifiers") or []) + (parent.get("modifiers") or []):
                if mod.get("field") != "hidden":
                    continue
                for cond in condition_child_ids(mod):
                    name = detachment_names.get(cond.get("childId"))
                    if name:
                        record["detachments"].add(name)

    all_enhancements = [{**e, "detachments": sorted(e["detachments"])}
                        for e in by_id.values()]
    all_enhancements.sort(key=lambda e: (e["faction"], e["name"]))
    all_detachments.sort(key=lambda d: (d["faction"], d["name"]))
    sizes = battle_sizes(next(r for r in roots if r.get("type") == "gameSystem"))

    (DATA / "battle_sizes.json").write_text(
        json.dumps(sizes, indent=1, ensure_ascii=False) + "\n")

    factions.sort(key=lambda f: f["name"])
    (DATA / "factions.json").write_text(
        json.dumps(factions, indent=1, ensure_ascii=False) + "\n")
    (DATA / "weapons.json").write_text(
        json.dumps(sorted(all_weapons.values(), key=lambda w: w["name"] or ""),
                   indent=1, ensure_ascii=False) + "\n")

    # El MFM oficial manda sobre BSData en puntos, destacamentos y realces.
    # Lo que solo existe en BSData se conserva, marcado como tal.
    catalogue_sizes = {f["name"]: f["unit_count"] for f in factions}
    mfm_points, mfm_dets, mfm_enh, mfm_leaders, mfm_meta = mfm.load(catalogue_sizes)

    all_detachments = merge_sources(all_detachments, mfm_dets,
                                    ("objective", "unique_tag"))
    all_enhancements = merge_enhancements(all_enhancements, mfm_enh)

    (DATA / "detachments.json").write_text(
        json.dumps(all_detachments, indent=1, ensure_ascii=False) + "\n")
    (DATA / "enhancements.json").write_text(
        json.dumps(all_enhancements, indent=1, ensure_ascii=False) + "\n")
    (DATA / "points.json").write_text(
        json.dumps(mfm_points, indent=1, ensure_ascii=False) + "\n")
    (DATA / "catalogue_links.json").write_text(
        json.dumps(links, indent=1, ensure_ascii=False) + "\n")

    build_db(factions, all_units, all_weapons, all_detachments,
             all_enhancements, sizes, mfm_points, mfm_leaders, mfm_meta, links)
    print(f"{len(factions)} catálogos | {len(all_units)} unidades | "
          f"{len(all_weapons)} perfiles de arma")
    print(f"{len(all_detachments)} destacamentos | {len(all_enhancements)} realces | "
          f"{len(sizes)} tamaños de partida")
    print(f"MFM v{mfm_meta.get('version')} ({mfm_meta.get('updated')}): "
          f"{len(mfm_points)} costes | {len(mfm_leaders)} adscripciones de líder")
    print(f"{len(links)} herencias entre catálogos")
    print(f"data/ y {DB.name} regenerados")


def build_db(factions, units, weapons, detachments, enhancements, sizes,
             mfm_points, mfm_leaders, mfm_meta, links):
    DB.unlink(missing_ok=True)
    con = sqlite3.connect(DB)
    con.executescript("""
      create table factions (id text primary key, name text, is_library int, unit_count int);
      create table units (id text primary key, faction_id text, faction text, name text,
                          single_model int, points_base int, max_in_army int);
      create table battle_sizes (name text, points int, detachment_points int, enhancements int);
      create table detachments (faction text, name text, detachment_points int,
                                objective text, unique_tag text, source text);
      create table enhancements (faction text, name text, points int,
                                 detachment text, source text);
      create table mfm_points (faction text, unit text, unit_norm text,
                               copies_from int, copies_to int, models int, points int);
      create table leaders (faction text, leader text, leader_norm text,
                            attach_to text, attach_to_norm text);
      create table mfm_meta (version text, updated text);
      create table catalogue_links (faction text, inherits_from text);
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
    con.executemany("insert or ignore into units values (?,?,?,?,?,?,?)",
                    [(u["id"], u["faction_id"], u["faction"], u["name"], int(u["single_model"]),
                      u["points"][0]["pts"] if u["points"] else None, u["max_in_army"])
                     for u in units])
    con.executemany("insert into battle_sizes values (?,?,?,?)",
                    [(s["name"], s.get("points"), s.get("detachment_points"),
                      s.get("enhancements")) for s in sizes])
    con.executemany("insert into detachments values (?,?,?,?,?,?)",
                    [(d["faction"], d["name"], d.get("detachment_points"),
                      d.get("objective"), d.get("unique_tag"), d["source"])
                     for d in detachments])
    con.executemany("insert into enhancements values (?,?,?,?,?)",
                    [(e["faction"], e["name"], e.get("points"), e.get("detachment"),
                      e["source"]) for e in enhancements])
    con.executemany("insert into mfm_points values (?,?,?,?,?,?,?)",
                    [(p["faction"], p["unit"], p["unit_norm"], p["copies_from"],
                      p["copies_to"], p["models"], p["points"]) for p in mfm_points])
    con.executemany("insert into leaders values (?,?,?,?,?)",
                    [(l["faction"], l["leader"], l["leader_norm"], l["attach_to"],
                      l["attach_to_norm"]) for l in mfm_leaders])
    con.execute("insert into mfm_meta values (?,?)",
                (mfm_meta.get("version"), mfm_meta.get("updated")))
    con.executemany("insert into catalogue_links values (?,?)",
                    [(l["faction"], l["inherits_from"]) for l in links])
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
      create index mfm_points_idx on mfm_points(faction, unit_norm);
      create index detachments_idx on detachments(faction, name);
      create index enhancements_idx on enhancements(faction, name);
      create index leaders_idx on leaders(faction, attach_to_norm);
      create index catalogue_links_idx on catalogue_links(faction);
    """)
    con.commit()
    con.close()


if __name__ == "__main__":
    main()
