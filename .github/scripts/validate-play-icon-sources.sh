#!/usr/bin/env bash
set -euo pipefail

targets=${1:-.github/play-icons/targets.tsv}
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

while IFS='|' read -r name package url; do
  slug=$(printf '%s' "$package" | tr '.-' '__')
  src="$workdir/$slug-source"
  out="$workdir/$slug.png"

  curl --fail --silent --show-error --location "$url" --output "$src"
  if grep -aq '<svg' "$src"; then
    if command -v rsvg-convert >/dev/null 2>&1; then
      rsvg-convert -w 512 -h 512 "$src" -o "$out"
    else
      inkscape "$src" --export-type=png --export-filename="$out" \
        --export-width=512 --export-height=512 >/dev/null 2>&1
    fi
  else
    convert "$src" -resize 512x512\! PNG32:"$out"
  fi

  test "$(identify -format '%wx%h' "$out")" = '512x512'
  test "$(stat -c%s "$out")" -lt 1048576
  printf '%s\t%s\t%s\n' "$name" "$package" "$(sha256sum "$out" | cut -d' ' -f1)"
done < "$targets"
