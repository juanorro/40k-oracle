#!/usr/bin/env bash
# Descarga o actualiza las fuentes de datos de 11ª edición.
# sources/ está fuera de git: es material de terceros, regenerable.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p sources

sync_repo() {
  local name="$1" url="$2"
  if [ -d "sources/$name/.git" ]; then
    echo "Actualizando $name..."
    git -C "sources/$name" fetch --depth 1 origin main -q
    git -C "sources/$name" reset --hard origin/main -q
  else
    echo "Clonando $name..."
    git clone --depth 1 -q "$url" "sources/$name"
  fi
  echo "  $name @ $(git -C "sources/$name" log -1 --format=%cd --date=short)"
}

sync_repo wh40k-11e     https://github.com/BSData/wh40k-11e.git
sync_repo wh40k-11e-mfm https://github.com/BSData/wh40k-11e-mfm.git
