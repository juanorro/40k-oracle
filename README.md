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

## Validar listas

```bash
python3 scripts/validate.py lists/ejemplo-death-guard.json
```

## Estado

Sobre 45 catálogos: 1.518 unidades, 5.364 perfiles de arma, 267 destacamentos,
877 realces y los tres tamaños de partida con sus límites.

Huecos conocidos:

- 8 unidades sin línea de características (0,5%) y 38 sin puntos (2,5%), por
  enlaces entre catálogos sin resolver.
- 74 de 267 destacamentos tienen menos de 4 realces y 8 realces no dicen a qué
  destacamento pertenecen. Parece hueco de la fuente, que lleva dos meses viva.

Todavía no se extraen las estratagemas ni las reglas de destacamento.

## Estructura

Ver [CLAUDE.md](CLAUDE.md) para el esquema de datos y las reglas de consulta.
