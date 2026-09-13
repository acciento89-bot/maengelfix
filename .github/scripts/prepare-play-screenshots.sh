#!/usr/bin/env bash
set -euo pipefail

manifest="${1:?manifest path required}"
output="${2:?output directory required}"
manifest_dir="$(cd "$(dirname "$manifest")" && pwd)"

test -s "$manifest"
test ! -e "$output"
mkdir -p "$output"

scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT

fetch_source() {
  local source="$1"
  local destination="$2"
  if [[ "$source" == local:* ]]; then
    cp "$manifest_dir/${source#local:}" "$destination"
  else
    curl --fail --silent --show-error --location --retry 3 "$source" --output "$destination"
  fi
}

prepare_group() {
  local package="$1"
  local group="$2"
  local sources="$3"
  local destination="$output/$package/$group"
  local index=0 source raw rgb left right center rendered metric channels

  mkdir -p "$destination"
  IFS=',' read -r -a source_list <<< "$sources"
  for source in "${source_list[@]}"; do
    index=$((index + 1))
    raw="$scratch/$package-$group-$index-raw.png"
    rgb="$scratch/$package-$group-$index-rgb.png"
    left="$scratch/$package-$group-$index-left.png"
    right="$scratch/$package-$group-$index-right.png"
    center="$scratch/$package-$group-$index-center.png"
    rendered="$destination/$(printf '%02d' "$index").png"

    fetch_source "$source" "$raw"
    test "$(identify -format '%wx%h' "$raw")" = '1080x2400'
    convert "$raw" -alpha remove -alpha off PNG24:"$rgb"
    convert "$rgb" -crop 1x2400+0+0 +repage -filter point -resize 135x2400\! PNG24:"$left"
    convert "$rgb" -crop 1x2400+1079+0 +repage -filter point -resize 135x2400\! PNG24:"$right"
    convert -size 1350x2400 xc:black \
      "$left" -geometry +0+0 -composite \
      "$rgb" -geometry +135+0 -composite \
      "$right" -geometry +1215+0 -composite \
      PNG24:"$rendered"

    test "$(identify -format '%wx%h' "$rendered")" = '1350x2400'
    channels="$(identify -format '%[channels]' "$rendered")"
    ! grep -qi a <<< "$channels"
    convert "$rendered" -crop 1080x2400+135+0 +repage PNG24:"$center"
    metric="$(compare -metric AE "$rgb" "$center" null: 2>&1 || true)"
    test "$metric" = '0'
  done
}

while IFS='|' read -r name package defaults english extra; do
  [[ -z "$name" || "$name" == \#* ]] && continue
  test -n "$package"
  test -z "${extra:-}"
  prepare_group "$package" default "$defaults"
  if [[ "$english" != '-' ]]; then
    prepare_group "$package" en-US "$english"
  fi
done < "$manifest"
