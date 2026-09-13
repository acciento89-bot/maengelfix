#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
manifest="$root/.github/play-screenshots/targets.tsv"
prepare="$root/.github/scripts/prepare-play-screenshots.sh"
sync="$root/.github/scripts/sync-all-play-screenshots.sh"
workflow="$root/.github/workflows/sync-all-play-screenshots.yml"

test -s "$manifest"
test -s "$prepare"
test -s "$sync"
test -s "$workflow"

mapfile -t rows < <(grep -vE '^[[:space:]]*(#|$)' "$manifest")
test "${#rows[@]}" -eq 22

expected="$(mktemp)"
actual="$(mktemp)"
trap 'rm -f "$expected" "$actual"' EXIT
cat > "$expected" <<'PACKAGES'
com.kamilunavo.kintaroq
com.kamilunavo.maengelfix
com.kamilunavo.onemoretap
com.kamilunavo.schonerledigt
de.kamilunav.kaltecalc
de.kamilunavo.arbeitsklar
de.kamilunavo.brennercalc
de.kamilunavo.heizkorpercalc
de.kamilunavo.hydrocalc
de.kamilunavo.idlehandwerker
de.kamilunavo.keepmeter
de.kamilunavo.luftungscalc
de.kamilunavo.magcalc
de.kamilunavo.navopass
de.kamilunavo.ninenine
de.kamilunavo.rapportai
de.kamilunavo.reklaio
de.kamilunavo.rohrcalc
de.kamilunavo.servicecheck
de.kamilunavo.volumecalc
de.kamilunavo.waermetakt
de.kamilunavo.zweicheck
PACKAGES
printf '%s\n' "${rows[@]}" | cut -d'|' -f2 | sort > "$actual"
diff -u "$expected" "$actual"

if grep -Eiq 'navokids|one more floor|deadreach|heizbalance|nächste runde|naechste runde' "$manifest"; then
  echo 'Excluded app found in Play screenshot targets.' >&2
  exit 1
fi

while IFS='|' read -r name package defaults english extra; do
  [[ -z "$name" || "$name" == \#* ]] && continue
  test -n "$package"
  test -z "${extra:-}"
  for group in "$defaults" "$english"; do
    [[ "$group" == '-' ]] && continue
    IFS=',' read -r -a urls <<< "$group"
    test "${#urls[@]}" -ge 2
    test "${#urls[@]}" -le 4
    for url in "${urls[@]}"; do
      if [[ "$url" == local:* ]]; then
        [[ "$url" =~ ^local:[A-Za-z0-9._/-]+\.png$ ]]
      else
        [[ "$url" =~ ^https://raw\.githubusercontent\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[0-9a-f]{40}/[^\|,]+\.png$ ]]
      fi
      [[ "$url" != *'/main/'* ]]
    done
  done
done < "$manifest"

grep -Fq 'runs-on: ubuntu-latest' "$workflow"
! grep -Eiq 'runs-on:[[:space:]]*macos|xcode|ios simulator' "$workflow"
grep -Fq 'github.event_name != '\''pull_request'\''' "$workflow"
grep -Fq 'phoneScreenshots:deleteall' "$sync"
grep -Fq 'phoneScreenshots?uploadType=media' "$sync"
grep -Fq 'changesNotSentForReview=true' "$sync"

fixture="$(mktemp -d)"
trap 'rm -f "$expected" "$actual"; rm -rf "$fixture"' EXIT
mkdir -p "$fixture/fixtures"
convert -size 1080x2400 gradient:'#113355-#44aa88' -alpha set -channel A -evaluate set 82% "$fixture/fixtures/a.png"
convert -size 1080x2400 gradient:'#552244-#ee8844' -alpha set -channel A -evaluate set 73% "$fixture/fixtures/b.png"
printf 'Fixture|de.example.fixture|local:fixtures/a.png,local:fixtures/b.png|-\n' > "$fixture/targets.tsv"
bash "$prepare" "$fixture/targets.tsv" "$fixture/out"

for index in 01 02; do
  output="$fixture/out/de.example.fixture/default/$index.png"
  input="$fixture/fixtures/$([[ "$index" == 01 ]] && printf a || printf b).png"
  test "$(identify -format '%wx%h' "$output")" = '1350x2400'
  ! identify -format '%[channels]' "$output" | grep -qi a
  convert "$output" -crop 1080x2400+135+0 +repage "$fixture/center.png"
  convert "$input" -alpha remove -alpha off PNG24:"$fixture/input-rgb.png"
  test "$(compare -metric AE "$fixture/input-rgb.png" "$fixture/center.png" null: 2>&1 || true)" = '0'
done
