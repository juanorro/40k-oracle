# Contribuir

*[In English](CONTRIBUTING.md)*

## La regla dura

**Nada de texto de reglas.** Este proyecto extrae hechos: nombres,
características numéricas, puntos, keywords y la estructura de las opciones de
construcción. No extrae, guarda ni redistribuye la redacción de reglas,
habilidades, estratagemas ni trasfondo. De todo eso se guarda solo el nombre,
como referencia a la publicación oficial.

Un pull request que incorpore texto de reglas no se fusionará, por útil que
fuese. Ver [NOTICE](NOTICE).

Tampoco se commitea nada bajo `data/`, `sources/` ni `index.db`: son generados
y están deliberadamente fuera de git.

## Puesta en marcha

```bash
pip install -r requirements.txt
./scripts/sync-sources.sh
python3 scripts/build.py
python3 -m unittest discover -s tests
```

## Cómo encaja todo

```
sources/wh40k-11e       catálogos BSData (JSON, esquema BattleScribe)
sources/wh40k-11e-mfm   mirror del Munitorum Field Manual (YAML)
        │
        ├── scripts/mfm.py     lee el MFM: puntos, destacamentos, líderes
        └── scripts/build.py   lee BSData y fusiona el MFM por encima
                │
                ├── data/*.json    salida inspeccionable
                └── index.db       SQLite, lo que consulta todo lo demás
        │
        ├── scripts/names.py    una sola normalización, compartida
        ├── scripts/query.py    resolución de facción y lecturas comunes
        ├── scripts/faction.py  el dosier de facción
        └── scripts/changes.py  diff tras un dataslate, revalida listas
```

`scripts/validate.py` solo lee `index.db`. Nunca parsea las fuentes.

## Lo que te va a morder

El esquema de BattleScribe es más sutil de lo que parece, y cada uno de estos
puntos ya ha provocado un bug real:

- **Los árboles de condiciones son booleanos.** Las condiciones de un modifier
  se anidan en grupos `and`/`or`, a veces varios niveles. Si los aplanas,
  aplicarás límites al tamaño de partida equivocado.
- **Los bloques `repeats` gobiernan los modifiers.** Un `increment` con
  `repeats` se aplica una vez por selección contada — cero si no hay ninguna.
- **Un `model` de nivel superior es una unidad; uno anidado es un miembro de
  escuadra.** Confundirlos pierde todos los personajes y vehículos del juego.
- **Los perfiles se esconden en tres sitios**: en la entrada, en un modelo hijo,
  o detrás de un `infoLink` a un perfil compartido.
- **El MFM tarifa por techos.** Una unidad con más modelos que el mínimo de su
  tramo paga el tramo siguiente, no el actual.

Si tocas cualquiera de estos, añade un test de regresión.
`tests/test_build.py` documenta la forma de cada bug que se coló antes.

## Estilo

- Python 3.11+, biblioteca estándar más PyYAML. Resiste añadir dependencias.
- Comentarios en inglés, explicando el *porqué*, no el *qué*.
- Funciones pequeñas, retornos tempranos, nada de one-liners ingeniosos en el
  código de parseo.

## Informar de datos erróneos

Si un coste o un perfil parece mal, mira primero la fuente: casi siempre está
aguas arriba. Los problemas de puntos van a
[wh40k-11e-mfm](https://github.com/BSData/wh40k-11e-mfm); los de unidades y
wargear a [wh40k-11e](https://github.com/BSData/wh40k-11e). Abre una issue aquí
si el fallo es de la extracción.
