#!/usr/bin/env bash
set -euo pipefail

manifest="${1:?manifest path required}"
prepared="${2:?prepared screenshot directory required}"
: "${TOKEN:?TOKEN is required}"

api='https://androidpublisher.googleapis.com/androidpublisher/v3'
upload='https://androidpublisher.googleapis.com/upload/androidpublisher/v3'
report="${RUNNER_TEMP:?RUNNER_TEMP is required}/play-screenshot-sync.tsv"
: > "$report"

abort_edit() {
  local package="$1" edit="$2"
  curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" \
    "$api/applications/$package/edits/$edit" >/dev/null || true
}

sync_one() {
  local name="$1" package="$2"
  local body status edit langs lang source_dir expected_count expected_sha actual_count actual_sha
  local fresh commit_mode='submitted'

  body="$(mktemp)"
  status="$(curl -sS -o "$body" -w '%{http_code}' -X POST \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' \
    "$api/applications/$package/edits")"
  if [[ "$status" != 2* ]]; then
    printf '%s\t%s\tEDIT_%s\n' "$name" "$package" "$status" >> "$report"
    return 0
  fi
  edit="$(jq -r '.id' "$body")"

  body="$(mktemp)"
  status="$(curl -sS -o "$body" -w '%{http_code}' \
    -H "Authorization: Bearer $TOKEN" \
    "$api/applications/$package/edits/$edit/listings")"
  if [[ "$status" != 2* ]]; then
    printf '%s\t%s\tLISTINGS_%s\n' "$name" "$package" "$status" >> "$report"
    abort_edit "$package" "$edit"
    return 0
  fi
  langs="$(jq -r '.listings[]?.language' "$body")"
  if [[ -z "$langs" ]]; then
    printf '%s\t%s\tNO_LISTINGS\n' "$name" "$package" >> "$report"
    abort_edit "$package" "$edit"
    return 0
  fi

  while IFS= read -r lang; do
    source_dir="$prepared/$package/default"
    if [[ "$lang" == en-* && -d "$prepared/$package/en-US" ]]; then
      source_dir="$prepared/$package/en-US"
    fi
    mapfile -t images < <(find "$source_dir" -maxdepth 1 -type f -name '*.png' | sort)
    expected_count="${#images[@]}"
    test "$expected_count" -ge 2

    body="$(mktemp)"
    status="$(curl -sS -o "$body" -w '%{http_code}' -X DELETE \
      -H "Authorization: Bearer $TOKEN" \
      "$api/applications/$package/edits/$edit/listings/$lang/phoneScreenshots:deleteall")"
    if [[ "$status" != 2* ]]; then
      printf '%s\t%s\tDELETE_%s_%s\n' "$name" "$package" "$lang" "$status" >> "$report"
      abort_edit "$package" "$edit"
      return 0
    fi

    for image in "${images[@]}"; do
      body="$(mktemp)"
      status="$(curl -sS -o "$body" -w '%{http_code}' -X POST \
        -H "Authorization: Bearer $TOKEN" -H 'Content-Type: image/png' --data-binary "@$image" \
        "$upload/applications/$package/edits/$edit/listings/$lang/phoneScreenshots?uploadType=media")"
      if [[ "$status" != 2* ]]; then
        printf '%s\t%s\tUPLOAD_%s_%s\n' "$name" "$package" "$lang" "$status" >> "$report"
        abort_edit "$package" "$edit"
        return 0
      fi
    done
  done <<< "$langs"

  body="$(mktemp)"
  status="$(curl -sS -o "$body" -w '%{http_code}' -X POST \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' \
    "$api/applications/$package/edits/$edit:commit")"
  if [[ "$status" != 2* ]]; then
    if ! grep -Fq 'Changes cannot be sent for review automatically' "$body"; then
      printf '%s\t%s\tCOMMIT_%s\n' "$name" "$package" "$status" >> "$report"
      abort_edit "$package" "$edit"
      return 0
    fi
    commit_mode='manual-review-required'
    body="$(mktemp)"
    status="$(curl -sS -o "$body" -w '%{http_code}' -X POST \
      -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' \
      "$api/applications/$package/edits/$edit:commit?changesNotSentForReview=true")"
  fi
  if [[ "$status" != 2* ]]; then
    printf '%s\t%s\tCOMMIT_%s\n' "$name" "$package" "$status" >> "$report"
    abort_edit "$package" "$edit"
    return 0
  fi

  fresh="$(curl -fsS -X POST -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' -d '{}' \
    "$api/applications/$package/edits" | jq -r '.id')"
  while IFS= read -r lang; do
    source_dir="$prepared/$package/default"
    if [[ "$lang" == en-* && -d "$prepared/$package/en-US" ]]; then
      source_dir="$prepared/$package/en-US"
    fi
    expected_count="$(find "$source_dir" -maxdepth 1 -type f -name '*.png' | wc -l | tr -d ' ')"
    expected_sha="$(sha256sum "$source_dir"/*.png | awk '{print $1}' | sort | tr '\n' ' ')"
    body="$(mktemp)"
    status="$(curl -sS -o "$body" -w '%{http_code}' \
      -H "Authorization: Bearer $TOKEN" \
      "$api/applications/$package/edits/$fresh/listings/$lang/phoneScreenshots")"
    if [[ "$status" != 2* ]]; then
      printf '%s\t%s\tVERIFY_HTTP_%s_%s\n' "$name" "$package" "$lang" "$status" >> "$report"
      abort_edit "$package" "$fresh"
      return 0
    fi
    actual_count="$(jq '.images | length' "$body")"
    actual_sha="$(jq -r '.images[]?.sha256' "$body" | sort | tr '\n' ' ')"
    if [[ "$actual_count" != "$expected_count" || "$actual_sha" != "$expected_sha" ]]; then
      printf '%s\t%s\tVERIFY_MISMATCH_%s\n' "$name" "$package" "$lang" >> "$report"
      abort_edit "$package" "$fresh"
      return 0
    fi
  done <<< "$langs"
  abort_edit "$package" "$fresh"
  printf '%s\t%s\tOK\t%s\n' "$name" "$package" "$commit_mode" >> "$report"
}

while IFS='|' read -r name package defaults english extra; do
  [[ -z "$name" || "$name" == \#* ]] && continue
  sync_one "$name" "$package"
done < "$manifest"

cat "$report"
test "$(grep -c $'\tOK\t' "$report")" -eq 22
if grep -v $'\tOK\t' "$report" | grep -q .; then
  echo 'At least one Google Play screenshot update failed.' >&2
  exit 1
fi
