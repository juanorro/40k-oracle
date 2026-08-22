#!/usr/bin/env python3
"""Valida una lista de ejército contra los datos extraídos en index.db.

Uso:  python3 scripts/validate.py lists/mi-lista.json

Los puntos salen del Munitorum Field Manual oficial. Si una unidad no aparece
en él se recurre a BSData y se avisa, porque BSData se queda corto en los
escalones de escuadra grande.
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "index.db"


def norm(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def ok(self):
        return not self.errors


def mfm_cost(con, faction, unit_name, models, copy_index, report):
    """Coste oficial del ejemplar nº `copy_index` de la unidad.

    Los tramos del MFM son techos: con más modelos que el mínimo se paga el
    escalón siguiente. Las Requisition Thresholds encarecen las copias extra.
    """
    query = ("select models, points from mfm_points where faction=? and unit_norm in (?,?,?) "
             "and copies_from<=? and (copies_to is null or copies_to>=?) order by models")
    # El MFM alterna singular y plural respecto a BSData.
    keys = (norm(unit_name), norm(unit_name) + "s", norm(unit_name).rstrip("s"))
    rows = con.execute(query, (faction, *keys, copy_index, copy_index)).fetchall()

    if not rows:
        # Hay unidades que viven en un catalogo y el MFM las tarifa en otro
        # (capitulos de Marines, Tiranidos, marines de culto). Se acepta el
        # precio si viene de una sola faccion, y se avisa de cual.
        elsewhere = con.execute(
            "select distinct faction from mfm_points where unit_norm in (?,?,?)",
            keys).fetchall()
        if len(elsewhere) != 1:
            return None
        source = elsewhere[0][0]
        rows = con.execute(query, (source, *keys, copy_index, copy_index)).fetchall()
        if rows:
            report.warn(f"«{unit_name}»: el MFM lo tarifa bajo {source}.")
    if not rows:
        return None
    for listed, points in rows:
        if models <= listed:
            return points
    report.warn(f"«{unit_name}»: {models} modelos supera el máximo del MFM "
                f"({rows[-1][0]}); se cobra ese escalón.")
    return rows[-1][1]


def bsdata_cost(con, unit_id, models):
    row = con.execute(
        "select pts from unit_points where unit_id=? and min_models<=? "
        "order by min_models desc limit 1", (unit_id, models)).fetchone()
    return row[0] if row else None


def resolve_unit(con, faction, name, report):
    row = con.execute(
        "select id, name, max_in_army, single_model from units where faction=? and name=?",
        (faction, name)).fetchone()
    if row:
        return row
    near = [r[0] for r in con.execute(
        "select name from units where faction=? and name like ? limit 3",
        (faction, f"%{name}%"))]
    hint = f" ¿Quisiste decir {', '.join(near)}?" if near else ""
    report.error(f"Unidad desconocida en {faction}: «{name}».{hint}")
    return None


def check_detachments(con, faction, names, report):
    chosen, spent, tags = [], 0, {}
    for name in names or []:
        row = con.execute(
            "select name, detachment_points, unique_tag from detachments "
            "where faction=? and name=? collate nocase", (faction, name)).fetchone()
        if row is None:
            report.error(f"Destacamento desconocido en {faction}: «{name}».")
            continue
        det_name, dp, tag = row
        chosen.append(det_name)
        spent += dp or 0
        if tag:
            if tag in tags:
                report.error(f"«{det_name}» y «{tags[tag]}» comparten la etiqueta "
                             f"Unique «{tag}»; no puedes llevar los dos.")
            tags[tag] = det_name
    if not chosen:
        report.error("La lista no declara ningún destacamento.")
    return chosen, spent


def check_enhancement(con, faction, enh, unit_id, unit_name, chosen, report):
    rows = con.execute(
        "select points, detachment from enhancements where faction=? and name=? collate nocase",
        (faction, enh)).fetchall()
    if not rows:
        report.error(f"Realce desconocido en {faction}: «{enh}».")
        return 0
    if not con.execute("select 1 from unit_keywords where unit_id=? and keyword='Character'",
                       (unit_id,)).fetchone():
        report.error(f"«{enh}» va sobre «{unit_name}», que no es Personaje.")

    owners = [d for _, d in rows if d]
    if owners and not {norm(o) for o in owners} & {norm(c) for c in chosen}:
        report.error(f"«{enh}» pertenece a {', '.join(sorted(set(owners)))}, "
                     f"que no está en la lista.")
    elif not owners:
        report.warn(f"«{enh}»: el catálogo no dice a qué destacamento pertenece.")
    return rows[0][0] or 0


def validate(path):
    army = json.loads(Path(path).read_text())
    report = Report()
    con = sqlite3.connect(DB)

    size = con.execute(
        "select name, points, detachment_points, enhancements from battle_sizes where name=?",
        (army.get("battle_size"),)).fetchone()
    if size is None:
        options = [r[0] for r in con.execute("select name from battle_sizes")]
        report.error(f"Tamaño de partida desconocido: «{army.get('battle_size')}». "
                     f"Disponibles: {', '.join(options)}.")
        return report, None
    size_name, pts_limit, dp_budget, enh_cap = size
    faction = army.get("faction")

    chosen, dp_spent = check_detachments(con, faction, army.get("detachments"), report)
    if dp_spent > dp_budget:
        report.error(f"Destacamentos: {dp_spent} DP sobre un presupuesto de {dp_budget}.")

    total, seen, characters, enh_used = 0, {}, 0, 0
    for item in army.get("units") or []:
        unit = resolve_unit(con, faction, item.get("name"), report)
        if unit is None:
            continue
        unit_id, unit_name, cap, single = unit
        models = 1 if single else item.get("models", 1)

        seen[unit_name] = seen.get(unit_name, 0) + 1
        cost = mfm_cost(con, faction, unit_name, models, seen[unit_name], report)
        if cost is None:
            cost = bsdata_cost(con, unit_id, models)
            if cost is None:
                report.warn(f"«{unit_name}»: sin puntos en ninguna fuente, no suma.")
                cost = 0
            else:
                report.warn(f"«{unit_name}»: no está en el MFM, se usa BSData "
                            f"({cost} pts), que puede quedarse corto.")
        total += cost

        if con.execute("select 1 from unit_keywords where unit_id=? and keyword='Character'",
                       (unit_id,)).fetchone():
            characters += 1
        if item.get("enhancement"):
            enh_used += 1
            total += check_enhancement(con, faction, item["enhancement"],
                                       unit_id, unit_name, chosen, report)

    for name, count in seen.items():
        cap = con.execute("select max_in_army from units where faction=? and name=?",
                          (faction, name)).fetchone()
        if cap and cap[0] and count > cap[0]:
            report.error(f"«{name}» aparece {count} veces; el máximo es {cap[0]}.")

    if characters == 0:
        # El force entry 'Army Roster' del sistema exige min 1 Character.
        report.error("La lista no lleva ningún Personaje y el reglamento exige al menos uno.")
    if enh_used > enh_cap:
        report.error(f"Realces: {enh_used} usados, el máximo en {size_name} es {enh_cap}.")
    if total > pts_limit:
        report.error(f"Puntos: {total} sobre un límite de {pts_limit} "
                     f"({total - pts_limit} de más).")

    version = con.execute("select version, updated from mfm_meta").fetchone()
    con.close()
    return report, {"total": total, "limit": pts_limit, "dp": dp_spent,
                    "dp_budget": dp_budget, "enh": enh_used, "enh_cap": enh_cap,
                    "mfm": version}


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python3 scripts/validate.py <lista.json>")
    if not DB.exists():
        sys.exit("Falta index.db. Ejecuta primero python3 scripts/build.py")

    report, totals = validate(sys.argv[1])
    if totals:
        version, updated = totals["mfm"] or ("?", "?")
        print(f"Puntos {totals['total']}/{totals['limit']} | "
              f"Destacamento {totals['dp']}/{totals['dp_budget']} | "
              f"Realces {totals['enh']}/{totals['enh_cap']}   "
              f"[MFM v{version}, {updated}]\n")
    for msg in report.warnings:
        print(f"  aviso  {msg}")
    for msg in report.errors:
        print(f"  ERROR  {msg}")
    print("\nLista legal." if report.ok() else f"\n{len(report.errors)} problema(s).")
    sys.exit(0 if report.ok() else 1)


if __name__ == "__main__":
    main()
