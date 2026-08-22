#!/usr/bin/env python3
"""Valida una lista de ejército contra los datos extraídos en index.db.

Uso:  python3 scripts/validate.py lists/mi-lista.json

Cada comprobación sale de un dato del catálogo, no de reglas escritas a mano,
salvo la de "al menos un Personaje", que viene del force entry del sistema.
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "index.db"


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def ok(self):
        return not self.errors


def points_for(con, unit_id, models):
    """Escalón aplicable: el de min_models más alto que no supere los modelos."""
    row = con.execute(
        "select pts from unit_points where unit_id=? and min_models<=? "
        "order by min_models desc limit 1", (unit_id, models)).fetchone()
    return row[0] if row else None


def resolve_unit(con, faction, name, report):
    rows = con.execute(
        "select id, name, points_base, max_in_army, single_model from units "
        "where faction=? and name=?", (faction, name)).fetchall()
    if not rows:
        near = con.execute(
            "select name from units where faction=? and name like ? limit 3",
            (faction, f"%{name}%")).fetchall()
        hint = f" ¿Quisiste decir {', '.join(r[0] for r in near)}?" if near else ""
        report.error(f"Unidad desconocida en {faction}: «{name}».{hint}")
        return None
    return rows[0]


def validate(path):
    army = json.loads(Path(path).read_text())
    report = Report()
    con = sqlite3.connect(DB)

    size = con.execute(
        "select name, points, detachment_points, enhancements from battle_sizes "
        "where name=?", (army.get("battle_size"),)).fetchone()
    if size is None:
        available = [r[0] for r in con.execute("select name from battle_sizes")]
        report.error(f"Tamaño de partida desconocido: «{army.get('battle_size')}». "
                     f"Disponibles: {', '.join(available)}.")
        return report, None
    _, pts_limit, dp_budget, enh_cap = size
    faction = army.get("faction")

    # --- Destacamentos -----------------------------------------------------
    chosen, dp_spent = [], 0
    for name in army.get("detachments") or []:
        row = con.execute(
            "select name, detachment_points from detachments where faction=? and name=?",
            (faction, name)).fetchone()
        if row is None:
            report.error(f"Destacamento desconocido en {faction}: «{name}».")
            continue
        chosen.append(row[0])
        dp_spent += row[1]
    if not chosen:
        report.error("La lista no declara ningún destacamento.")
    if dp_spent > dp_budget:
        report.error(f"Destacamentos: {dp_spent} puntos de destacamento sobre un "
                     f"presupuesto de {dp_budget}.")

    # --- Unidades ----------------------------------------------------------
    total, counts, characters = 0, {}, 0
    for item in army.get("units") or []:
        unit = resolve_unit(con, faction, item.get("name"), report)
        if unit is None:
            continue
        unit_id, unit_name, base, cap, single = unit
        models = 1 if single else item.get("models", 1)

        cost = points_for(con, unit_id, models)
        if cost is None:
            report.warn(f"«{unit_name}»: sin puntos en el catálogo, no suma al total.")
        else:
            total += cost

        counts[unit_name] = counts.get(unit_name, 0) + 1
        if con.execute("select 1 from unit_keywords where unit_id=? and keyword='Character'",
                       (unit_id,)).fetchone():
            characters += 1

        enh = item.get("enhancement")
        if enh:
            total += check_enhancement(con, faction, enh, unit_id, unit_name, chosen, report)

    for name, n in counts.items():
        cap = con.execute("select max_in_army from units where faction=? and name=?",
                          (faction, name)).fetchone()
        if cap and cap[0] and n > cap[0]:
            report.error(f"«{name}» aparece {n} veces; el máximo es {cap[0]}.")

    if characters == 0:
        # El force entry 'Army Roster' del sistema exige min 1 Character.
        report.error("La lista no lleva ningún Personaje y el reglamento exige al menos uno.")

    used = sum(1 for u in army.get("units") or [] if u.get("enhancement"))
    if used > enh_cap:
        report.error(f"Realces: {used} usados, el máximo en {size[0]} es {enh_cap}.")

    if total > pts_limit:
        report.error(f"Puntos: {total} sobre un límite de {pts_limit} "
                     f"({total - pts_limit} de más).")

    con.close()
    return report, {"total": total, "limit": pts_limit, "dp": dp_spent,
                    "dp_budget": dp_budget, "enh": used, "enh_cap": enh_cap}


def check_enhancement(con, faction, enh, unit_id, unit_name, chosen, report):
    row = con.execute("select id, points from enhancements where faction=? and name=?",
                      (faction, enh)).fetchone()
    if row is None:
        report.error(f"Realce desconocido en {faction}: «{enh}».")
        return 0
    enh_id, points = row
    if not con.execute("select 1 from unit_keywords where unit_id=? and keyword='Character'",
                       (unit_id,)).fetchone():
        report.error(f"«{enh}» va sobre «{unit_name}», que no es Personaje.")
    unlocks = [r[0] for r in con.execute(
        "select detachment from enhancement_detachments where enhancement_id=?", (enh_id,))]
    if unlocks and not set(unlocks) & set(chosen):
        report.error(f"«{enh}» pertenece a {', '.join(unlocks)}, "
                     f"que no está en la lista.")
    elif not unlocks:
        report.warn(f"«{enh}»: el catálogo no dice a qué destacamento pertenece.")
    return points or 0


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python3 scripts/validate.py <lista.json>")
    if not DB.exists():
        sys.exit("Falta index.db. Ejecuta primero python3 scripts/build.py")

    report, totals = validate(sys.argv[1])
    if totals:
        print(f"Puntos {totals['total']}/{totals['limit']} | "
              f"Destacamento {totals['dp']}/{totals['dp_budget']} | "
              f"Realces {totals['enh']}/{totals['enh_cap']}\n")
    for msg in report.warnings:
        print(f"  aviso  {msg}")
    for msg in report.errors:
        print(f"  ERROR  {msg}")
    print("\nLista legal." if report.ok() else f"\n{len(report.errors)} problema(s).")
    sys.exit(0 if report.ok() else 1)


if __name__ == "__main__":
    main()
