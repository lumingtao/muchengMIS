#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
NPM_VERSION="${NPM_VERSION:-11.7.0}"
NPM_DIR="$ROOT_DIR/tools/npm"
ARCHIVE="${TMPDIR:-/tmp}/npm-$NPM_VERSION.tgz"

mkdir -p "$NPM_DIR/cache" "$NPM_DIR/package"
curl -L --connect-timeout 15 --max-time 120 -o "$ARCHIVE" "https://registry.npmjs.org/npm/-/npm-$NPM_VERSION.tgz"
rm -rf "$NPM_DIR/package"
mkdir -p "$NPM_DIR/package"
tar -xzf "$ARCHIVE" -C "$NPM_DIR/package" --strip-components=1

echo "npm $NPM_VERSION installed under $NPM_DIR/package"
