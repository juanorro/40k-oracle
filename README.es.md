# 40k-oracle

Datos estructurados y consultables de **Warhammer 40.000, 11ª edición** —
pensados para que los lea un agente de IA y para comprobar que una lista de
ejército es legal.

*[Read this in English](README.md)*

Sin servidor, sin Docker, sin API. Un script de construcción, un fichero SQLite
y algo de JSON.

## Qué es

Una tubería que convierte los catálogos de la comunidad y el Munitorum Field
Manual oficial en un conjunto de datos que puedes consultar con exactitud:

- **1.518 unidades** con características, keywords y perfiles de arma
- **2.972 costes oficiales**, con escalones por tamaño de escuadra y
  Requisition Thresholds
- **395 destacamentos** con Detachment Points, Force Disposition y etiquetas Unique
- **1.440 realces**, cada uno vinculado al destacamento que lo desbloquea
- **2.137 adscripciones Leader/Support** — qué personaje puede unirse a qué unidad
- Un validador de listas que hace cumplir todo lo anterior

## Qué no es

- **No es una referencia de reglas.** No se extrae ni se almacena texto de
  reglas. De habilidades y estratagemas solo se guarda el nombre, como
  referencia a la fuente oficial.
- **No es un constructor con interfaz gráfica.** Para eso está
  [New Recruit](https://www.newrecruit.eu/). Esto es para consultar, analizar y validar.
- **No está afiliado a Games Workshop.** Ver [NOTICE](NOTICE).

## Arranque

```bash
pip install -r requirements.txt
./scripts/sync-sources.sh     # descarga ~75 MB de fuentes de terceros
python3 scripts/build.py      # genera data/ e index.db en un segundo
```

En este repositorio no se versiona nada más que código: el conjunto de datos se
construye en tu máquina y se queda ahí.

## Consultar

```bash
sqlite3 index.db "
  select u.name, p.points
  from units u join mfm_points p on p.unit_norm = lower(replace(u.name,' ',''))
  where u.faction like '%Death Guard%' order by p.points;"
```

Tablas principales:

| Tabla | Contiene |
|---|---|
| `units` | identidad, facción, si es de un solo modelo, máximo por ejército |
| `unit_profiles` | M, T, Sv, W, Ld, OC, salvación invulnerable |
| `mfm_points` | **costes oficiales**, por nº de modelos y nº de copia |
| `weapons`, `unit_weapons` | perfiles de arma y quién las lleva |
| `unit_loadout` | el equipo con el que la unidad viene de serie |
| `unit_keywords`, `unit_abilities` | keywords y nombres de habilidad |
| `battle_sizes` | límites de puntos, destacamento y realces |
| `detachments`, `enhancements` | opciones de construcción y qué las desbloquea |
| `leaders` | adscripciones Leader/Support |
| `catalogue_links` | de qué catálogos hereda unidades cada facción |

Esquema completo y reglas de interpretación: [CLAUDE.md](CLAUDE.md).

## Explorar una facción

```bash
python3 scripts/faction.py                       # lista todas las facciones
python3 scripts/faction.py "death guard"         # destacamentos, realces, unidades
python3 scripts/faction.py orks --keyword Battleline --max-points 120
```

Los nombres de facción son flexibles: `death guard`, `Death Guard` y `custodes`
resuelven a su catálogo.

## Validar una lista

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

Comprueba el límite de puntos (con umbrales de requisición), el presupuesto de
Detachment Points, etiquetas Unique en conflicto, el tope de realces y si cada
uno pertenece a un destacamento elegido y va sobre un Personaje, el máximo por
unidad, el mínimo de un Personaje, y si los líderes pueden unirse a las unidades
que se les asignan.

Todas las comprobaciones salen del catálogo. Ninguna es una regla escrita a mano.

## Enfrentarte a un rival

```bash
python3 scripts/analyse.py --threat "chaos space marines"
python3 scripts/analyse.py --threat "chaos space marines" --attacker "death guard"
python3 scripts/analyse.py --threat "chaos space marines" --attacker "death guard" --units
```

El perfil de amenaza toma una línea representativa por franja de resistencia
—chaff, infantería, élite, monstruo, vehículo pesado— así que cubre lo que una
facción **puede** plantar, en vez de adivinar una lista. Las armas se ordenan
por su **peor** bracket, porque una lista que tiene que responder a todo no
puede permitirse un arma excelente contra un objetivo e inútil contra el resto.

`--units` puntúa unidades enteras por 100 puntos usando el equipamiento por
defecto con el que la fuente las envía, tomado de los defaults declarados en
BSData. Cubre el 88% de las unidades jugables; el resto no tiene default
derivable.

El modelo de daño ignora Feel No Pain, cobertura, estratagemas, repeticiones y
reglas de ejército, y la puntuación por unidad ignora además durabilidad y
control de objetivo. Compara entradas entre sí; no predice una partida.

## Revisar una lista

```bash
python3 scripts/review.py lists/mi-lista.json --vs "chaos space marines"
```

Informa de modelos, heridas y control de objetivo, y del daño esperado por
franja de amenaza. Marca como **thin** cualquier franja por debajo de un tercio
de la más fuerte, y nombra las unidades que están haciendo ese trabajo — que
suele importar más que el hueco en sí, porque una sola unidad frágil cubriendo
una franja entera es un problema distinto de no tener respuesta.

El melé asume contacto, así que esa columna es un techo y no es comparable con
el disparo.

## Seguir los dataslates

```bash
python3 scripts/changes.py --snapshot
./scripts/sync-sources.sh && python3 scripts/build.py
python3 scripts/changes.py
```

Imprime cada movimiento de puntos, cambio de coste de destacamento y subida de
versión del MFM, y luego revalida todas las listas de `lists/` diciéndote cuáles
se han roto.

## Skills

`.claude/skills/` incluye tres skills para agentes que trabajen en este
repositorio: `faction-brief`, `build-list`, `review-list` y `sync-data`. Encierran los
procedimientos de arriba y una regla permanente: nunca escribir un valor de
puntos que no se haya leído de la base de datos.

## Por qué manda el Munitorum Field Manual

Los puntos salen del MFM oficial, no de BSData. De 890 costes comparados,
**119 discrepaban** — muchos por el doble exacto, porque a BSData le faltan los
escalones de escuadra grande:

```
Terminator Squad      10 modelos:  BSData=160   MFM=320
Deathwing Terminators 10 modelos:  BSData=165   MFM=330
Broadside Battlesuits  2 modelos:  BSData=75    MFM=150
```

Un validador que use puntos de BSData da por buenas listas muy por debajo de
puntos. Cuando una unidad no está en el MFM se usa BSData **y el validador lo dice**.

## Fuentes

- [BSData/wh40k-11e](https://github.com/BSData/wh40k-11e) — catálogos de la
  comunidad: unidades, perfiles, armas, opciones de wargear y restricciones.
- [BSData/wh40k-11e-mfm](https://github.com/BSData/wh40k-11e-mfm) — mirror del
  [Munitorum Field Manual](https://mfm.warhammer-community.com/en) oficial.

Ninguna está avalada por Games Workshop.

## Cobertura y huecos conocidos

- El MFM cubre el **95%** de las unidades de juego normal. El resto cae a BSData
  con aviso. Las unidades `[Legends]` y `[Crucible]` no están en el MFM por diseño.
- 8 unidades sin línea de características (0,5%).
- No se extraen estratagemas ni reglas de destacamento: son texto de reglas.

## Para agentes de IA

[CLAUDE.md](CLAUDE.md) es el contrato: esquema, reglas de interpretación y una
instrucción permanente — nunca cites puntos ni características de memoria,
consúltalos siempre en la base. Cambian con cada dataslate de balance.

## Contribuir

Ver [CONTRIBUTING.es.md](CONTRIBUTING.es.md). La regla dura: nada de texto de reglas.

## Licencia

Código bajo [licencia MIT](LICENSE). Los datos del juego no están cubiertos por
ella y no se distribuyen aquí — lee el [NOTICE](NOTICE).
