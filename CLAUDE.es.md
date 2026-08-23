# 40k-oracle — datos de Warhammer 40.000, 11ª edición

Base de conocimiento estructurada para consultar con un agente. No es una app:
no hay servidor, ni Docker, ni API. Son ficheros y una base SQLite.

*[In English](CLAUDE.md)*

## Regla principal

**Nunca cites de memoria puntos, características ni perfiles de arma.
Consúltalos siempre en `index.db` o en `data/`.** Estos valores cambian con cada
dataslate de balance, así que el conocimiento del modelo estará desactualizado.
Si un dato no está en el repositorio, dilo en vez de rellenarlo.

## Dónde está cada cosa

| Ruta | Qué es | Editable a mano |
|---|---|---|
| `index.db` | SQLite generado. Consultas exactas y agregaciones. | No, se regenera |
| `data/` | Mismo contenido en JSON, para inspeccionar. Fuera de git. | No, se regenera |
| `sources/` | Fuentes de terceros, descargadas. Fuera de git. | No |
| `scripts/` | `sync-sources.sh` descarga, `build.py` extrae. | Sí |
| `lists/` | Listas de ejército para validar. | Sí |
| `tests/` | Tests de regresión de la extracción. | Sí |

## Cómo consultar

```bash
sqlite3 index.db "select name, points_base from units where faction like '%Death Guard%' order by points_base;"
```

Esquema de `index.db`:

- `factions(id, name, is_library, unit_count)`
- `units(id, faction_id, faction, name, single_model, points_base, max_in_army)`
- `unit_profiles(unit_id, name, m, t, sv, w, ld, oc, invuln)` — características del modelo
- `unit_points(unit_id, min_models, pts)` — escalones de BSData por tamaño
- `unit_keywords(unit_id, keyword)`
- `unit_abilities(unit_id, ability)` — solo nombres
- `weapons(id, name, kind, range, attacks, skill, strength, ap, damage, keywords)`
- `unit_weapons(unit_id, weapon_id)` — todas las armas de sus opciones
- `unit_loadout(unit_id, model, count_min, count_max, weapon_id)` — solo el equipo por defecto
- `battle_sizes(name, points, detachment_points, enhancements)` — límites del ejército
- `detachments(faction, name, detachment_points, objective, unique_tag, source)`
- `enhancements(faction, name, points, detachment, source)` — una fila por realce y destacamento
- `mfm_points(faction, unit, unit_norm, copies_from, copies_to, models, points)` — **puntos oficiales**
- `leaders(faction, leader, leader_norm, attach_to, attach_to_norm)` — quién puede unirse a qué
- `mfm_meta(version, updated)` — qué Munitorum Field Manual está cargado
- `catalogue_links(faction, inherits_from)` — de qué catálogos hereda cada facción
- `faction_aliases(alias, alias_norm, faction, is_primary)` — todos los nombres de una facción

### De dónde salen los puntos

**`mfm_points` es la fuente autoritativa**, del Munitorum Field Manual oficial.
`unit_points` viene de BSData y se queda corto en los escalones de escuadra
grande — úsalo solo si el MFM no tiene la unidad, y dilo cuando lo hagas.

Reglas de tarificación del MFM:

- Los tramos son **techos**: si la unidad tiene más modelos que el mínimo de su
  tramo, pagas el tramo siguiente. Plague Marines con 6 modelos paga el precio
  de 7 (125), no el de 5.
- **Requisition Thresholds**: `copies_from`/`copies_to` acotan a qué ejemplar
  aplica el precio. Deathshroud Terminators cuesta 160 las dos primeras veces y
  170 a partir de la tercera.
- El MFM alterna singular y plural respecto a BSData, y a veces tarifa una
  unidad bajo otra facción (Plague Marines bajo Death Guard aunque figure en el
  catálogo de Chaos Space Marines).

### Leer el resto

- `unit_points` tiene un escalón por tamaño. Para N modelos aplica **el escalón
  de `min_models` más alto que no supere N**. Plague Marines: 90 con 5 modelos,
  125 desde 6, 180 desde 8.
- `single_model = 1` son personajes, vehículos y monstruos: una sola miniatura.
- Las características se guardan como texto (`5"`, `3+`, `D6+1`) porque así
  están en la fuente. Si necesitas calcular, parsea al vuelo.
- `invuln` vacío significa que no tiene salvación invulnerable.
- `max_in_army` es cuántas veces puede repetirse la unidad: 3 normalmente, 6 en
  Battleline.
- En 11ª los destacamentos **cuestan Detachment Points** (1-3 cada uno) y el
  ejército tiene un presupuesto según el tamaño de partida: 2 en Incursion, 3 en
  Strike Force, 4 en Onslaught. Puedes llevar varios.
- `unique_tag`: no puedes llevar dos destacamentos con la misma etiqueta.
- `objective` es la Force Disposition que otorga el destacamento.

## Explorar una facción

```bash
python3 scripts/faction.py "death guard"
python3 scripts/faction.py orks --keyword Battleline --max-points 120
```

Los nombres resuelven de forma flexible por `faction_aliases`, así que
`death guard` y `custodes` valen. Todo acepta ya nombres humanos, `validate.py`
incluido.

## Validar una lista

```bash
python3 scripts/validate.py lists/example-death-guard.json
```

La lista es un JSON con `faction`, `battle_size`, `detachments` y `units`. Cada
unidad lleva `name`, opcionalmente `models`, `enhancement` y `attached_to` (la
unidad a la que se une un líder). Ver
[lists/example-death-guard.json](lists/example-death-guard.json).

Comprueba el límite de puntos (con umbrales de requisición), el presupuesto de
destacamento, etiquetas Unique en conflicto, el tope de realces, que cada realce
corresponda a un destacamento elegido y vaya sobre un Personaje, el máximo de
repeticiones por unidad, que haya al menos un Personaje y que los líderes se
unan a unidades permitidas.

Las facciones de capítulo heredan unidades de su catálogo padre: Ultramarines
tiene 16 unidades propias y el resto salen de Space Marines. La resolución sigue
`catalogue_links` automáticamente.

Todas las comprobaciones salen del catálogo, no de reglas escritas a mano.

## Frontera deliberada

Se extraen **hechos**: nombres, números, keywords, estructura de opciones. **No
se extrae el texto de las reglas** — de las habilidades solo se guarda el
nombre, como referencia para buscarla en la fuente oficial.

Si te piden añadir texto de reglas literal al repositorio, dilo antes de hacerlo.

## Tras un dataslate

```bash
python3 scripts/changes.py --snapshot
./scripts/sync-sources.sh && python3 scripts/build.py
python3 scripts/changes.py
```

Diferencia puntos y costes de destacamento, y revalida `lists/`.

## Regenerar

```bash
./scripts/sync-sources.sh && python3 scripts/build.py
python3 -m unittest discover -s tests
```
