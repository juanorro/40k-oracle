# Warhammer 40.000 — 11ª edición

Repositorio de datos estructurados de 11ª edición, pensado para consultarse con
un agente de IA y para construir listas, comparar unidades y llevar la colección.

Sin dependencias: Python 3 y `sqlite3` del sistema.

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
  [Munitorum Field Manual](https://mfm.warhammer-community.com/en) oficial.

Ninguna está avalada por Games Workshop.

## Estado

1.518 unidades y 5.364 perfiles de arma sobre 45 catálogos.

Huecos conocidos, todos por resolver enlaces entre catálogos:

- 8 unidades sin línea de características (0,5%) — el perfil vive en otro catálogo.
- 38 unidades sin puntos (2,5%).

Todavía no se extraen: destacamentos, realces, estratagemas ni las restricciones
de construcción de lista. `scripts/build.py` es el sitio donde añadirlos.

## Estructura

Ver [CLAUDE.md](CLAUDE.md) para el esquema de datos y las reglas de consulta.
