# Warhammer 40.000 — 11ª edición

Repositorio de datos estructurados de 11ª edición, pensado para consultarse con
un agente de IA y para construir listas, comparar unidades y llevar la colección.

Requiere Python 3, `sqlite3` del sistema y PyYAML (`pip install pyyaml`).

## Arranque

```bash
./scripts/sync-sources.sh
python3 scripts/build.py
```

Esto descarga las fuentes a `sources/` (fuera de git) y genera `data/` e `index.db`.

## Fuentes

- [BSData/wh40k-11e](https://github.com/BSData/wh40k-11e) — catálogos de 11ª
  mantenidos por la comunidad.
- [BSData/wh40k-11e-mfm](https://github.com/BSData/wh40k-11e-mfm) — snapshots del
  [Munitorum Field Manual](https://mfm.warhammer-community.com/en) oficial, que es
  la **fuente autoritativa de puntos**. BSData se queda corto en los escalones de
  escuadra grande: de 890 costes comparados, 119 discrepaban.

Ninguna está avalada por Games Workshop.

## Validar listas

```bash
python3 scripts/validate.py lists/ejemplo-death-guard.json
```

## Estado

Sobre 45 catálogos: 1.518 unidades, 5.364 perfiles de arma, 385 destacamentos,
1.415 realces, 2.972 costes oficiales y 2.137 adscripciones de líder.

Huecos conocidos:

- El MFM cubre el 95% de las unidades de juego normal. El resto usa puntos de
  BSData y el validador lo avisa. Las unidades `[Legends]` y `[Crucible]` no
  están en el MFM por diseño.
- Las facciones de capítulo (Ultramarines, Imperial Fists…) tienen su propio
  catálogo pero la mayoría de sus unidades viven en el de Space Marines, y
  todavía no se resuelven entre catálogos: una lista de capítulo no valida bien.
- 8 unidades sin línea de características (0,5%).

Todavía no se extraen las estratagemas ni las reglas de destacamento, y el
validador no comprueba aún las adscripciones Leader/Support, cuyos datos ya
están en la tabla `leaders`.

## Estructura

Ver [CLAUDE.md](CLAUDE.md) para el esquema de datos y las reglas de consulta.
