#!/usr/bin/env python3
"""Lectura del Munitorum Field Manual oficial (snapshots de BSData/wh40k-11e-mfm).

El MFM es la fuente autoritativa de puntos: BSData se queda corto en los
escalones de escuadra grande. De aquí salen también las Requisition Thresholds,
las etiquetas Unique de destacamento y las adscripciones Leader/Support, que
BSData no modela.
"""
import re
from pathlib import Path

import yaml

MFM_DIR = Path(__file__).resolve().parent.parent / "sources" / "wh40k-11e-mfm" / "data"

# El MFM nombra las facciones de forma más corta que los catálogos de BSData.
FACTION_ALIASES = {
    "Aeldari": "Aeldari - Aeldari Library",
    "Drukhari": "Aeldari - Aeldari Library",
    "Astra Militarum": "Imperium - Astra Militarum - Library",
    "Chaos Daemons": "Chaos - Daemons Library",
    "Chaos Knights": "Chaos - Chaos Knights Library",
    "Imperial Knights": "Imperium - Imperial Knights - Library",
    "Imperial Agents": "Imperium - Agents of the Imperium",
    "Titan Legions": "Library - Titans",
    "Chaos Titan Legions": "Library - Titans",
}


def norm(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def parse_range(text):
    """'[1,)' -> (1, None); '[1,2]' -> (1, 2). Es el nº de copias en el ejército."""
    match = re.match(r"[\[(](\d+),\s*(\d*)[\])]", text or "")
    if not match:
        return 1, None
    low, high = match.groups()
    return int(low), int(high) if high else None


def match_faction(mfm_name, catalogues):
    """`catalogues` es {nombre de catalogo: numero de unidades}.

    Varios catalogos pueden acabar igual ('Library - Tyranids' y
    'Xenos - Tyranids'), asi que se elige el que mas unidades tiene, que es
    donde de verdad viven.
    """
    if mfm_name in FACTION_ALIASES:
        return FACTION_ALIASES[mfm_name]
    target = norm(mfm_name)
    candidates = [c for c in catalogues if norm(c).endswith(target)]
    return max(candidates, key=lambda c: catalogues[c]) if candidates else None


def load(catalogues):
    """Devuelve (puntos, destacamentos, realces, líderes, meta)."""
    points, detachments, enhancements, leaders = [], [], [], []
    meta = {}
    if not MFM_DIR.is_dir():
        return points, detachments, enhancements, leaders, meta

    for path in sorted(MFM_DIR.glob("*.yaml")):
        doc = yaml.safe_load(path.open())
        if path.name == "meta.yaml":
            meta = {"version": doc.get("version"), "updated": str(doc.get("lastUpdated"))}
            continue

        faction = match_faction(doc["name"], catalogues)
        if faction is None:
            continue

        for det in doc.get("detachments") or []:
            detachments.append({
                "faction": faction,
                "name": det.get("name"),
                "detachment_points": det.get("dp"),
                "objective": det.get("objective"),
                "unique_tag": det.get("unique"),
            })
            for enh in det.get("enhancements") or []:
                enhancements.append({
                    "faction": faction,
                    "name": enh.get("name"),
                    "points": enh.get("points"),
                    "detachment": det.get("name"),
                })

        for unit in doc.get("units") or []:
            name = unit.get("name")
            for block in unit.get("pricing") or []:
                low, high = parse_range(block.get("range"))
                for cost in block.get("costs") or []:
                    points.append({
                        "faction": faction,
                        "unit": name,
                        "unit_norm": norm(name),
                        "copies_from": low,
                        "copies_to": high,
                        "models": cost.get("models"),
                        "points": cost.get("points"),
                    })
            for target in unit.get("attachTo") or []:
                leaders.append({
                    "faction": faction,
                    "leader": name,
                    "leader_norm": norm(name),
                    "attach_to": target,
                    "attach_to_norm": norm(target),
                })

    return points, detachments, enhancements, leaders, meta
