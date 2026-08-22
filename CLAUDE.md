# Repositorio de datos de Warhammer 40.000 — 11ª edición

Base de conocimiento estructurada para consultar con un agente. No es una app:
no hay servidor, ni Docker, ni API. Son ficheros y una base SQLite.

## Regla principal

**Nunca cites de memoria puntos, características ni perfiles de arma. Consúltalos
siempre en `index.db` o en `data/`.** Los valores de 40k cambian con cada dataslate
de balance y el conocimiento del modelo estará desactualizado. Si un dato no está
en el repositorio, dilo en vez de rellenarlo.

## Dónde está cada cosa

| Ruta | Qué es | Editable a mano |
|---|---|---|
| `index.db` | SQLite generado. Para consultas exactas y agregaciones. | No, se regenera |
| `data/` | Mismo contenido en JSON, versionado en git para ver diffs. | No, se regenera |
| `notes/` | Notas propias: reglas explicadas, tácticas, dudas resueltas. | Sí |
| `collection/` | Miniaturas que tengo, estado de pintado, qué falta. | Sí |
| `sources/` | Clon de BSData. Fuera de git. | No |
| `scripts/` | `sync-sources.sh` descarga, `build.py` extrae. | Sí |

## Cómo consultar

```bash
sqlite3 index.db "select name, points_base from units where faction like '%Death Guard%' order by points_base;"
```

Esquema de `index.db`:

- `factions(id, name, is_library, unit_count)`
- `units(id, faction_id, faction, name, single_model, points_base, max_in_army)`
- `unit_profiles(unit_id, name, m, t, sv, w, ld, oc, invuln)` — características del modelo
- `unit_points(unit_id, min_models, pts)` — escalones por tamaño de unidad
- `unit_keywords(unit_id, keyword)`
- `unit_abilities(unit_id, ability)` — solo nombres
- `weapons(id, name, kind, range, attacks, skill, strength, ap, damage, keywords)`
- `unit_weapons(unit_id, weapon_id)`
- `battle_sizes(name, points, detachment_points, enhancements)` — límites del ejército
- `detachments(id, name, faction, detachment_points)`
- `enhancements(id, name, faction, points)`
- `enhancement_detachments(enhancement_id, detachment)` — qué realce desbloquea cada destacamento

Notas de interpretación:

- `unit_points` tiene un escalón por tamaño. Para N modelos aplica **el escalón
  de `min_models` más alto que no supere N**. Plague Marines: 90 con 5 modelos,
  125 desde 6, 180 desde 8.
- `single_model = 1` son personajes, vehículos y monstruos: una sola miniatura.
- Las características se guardan como texto (`5"`, `3+`, `D6+1`) porque así están
  en la fuente. Si necesitas calcular, parsea al vuelo.
- `invuln` vacío significa que no tiene salvación invulnerable.
- `max_in_army` es cuántas veces puede repetirse la unidad: 3 normalmente, 6 en
  Battleline.
- En 11ª los destacamentos **cuestan Detachment Points** (1-3 cada uno) y el
  ejército tiene un presupuesto según el tamaño de partida: 2 en Incursion,
  3 en Strike Force, 4 en Onslaught. Puedes llevar varios.

Para las notas, `grep -r` sobre `notes/` es suficiente.

## Validar una lista

```bash
python3 scripts/validate.py lists/ejemplo-death-guard.json
```

La lista es un JSON con `faction`, `battle_size`, `detachments` y `units`; cada
unidad lleva `name`, opcionalmente `models` y `enhancement`. Ver
[lists/ejemplo-death-guard.json](lists/ejemplo-death-guard.json).

Comprueba límite de puntos, presupuesto de destacamento, tope de realces, que
cada realce corresponda a un destacamento elegido y vaya sobre un Personaje,
el máximo de repeticiones por unidad y que haya al menos un Personaje.

Todas las comprobaciones salen del catálogo, no de reglas escritas a mano.

## Frontera deliberada

Se extraen **hechos**: nombres, números, keywords, estructura de opciones. **No se
extrae el texto de las reglas** — de las habilidades solo se guarda el nombre, como
referencia para buscarla en la fuente oficial. Las explicaciones en `notes/` son
redacción propia, no copiadas.

Si te piden añadir texto de reglas literal al repositorio, dilo antes de hacerlo.

## Regenerar

```bash
./scripts/sync-sources.sh && python3 scripts/build.py
```
