#!/usr/bin/env bash
set -euo pipefail

workflow=.github/workflows/sync-all-play-icons.yml
targets=.github/play-icons/targets.tsv

test -f "$workflow"
test -f "$targets"

grep -q '^  pull_request:$' "$workflow"
grep -q '^  validate:$' "$workflow"
grep -q "if: github.event_name != 'pull_request'" "$workflow"
grep -q '^    needs: validate$' "$workflow"

sync_line=$(grep -n '^  sync:$' "$workflow" | cut -d: -f1)
oidc_line=$(grep -n '^      id-token: write$' "$workflow" | cut -d: -f1)
test -n "$sync_line"
test -n "$oidc_line"
test "$oidc_line" -gt "$sync_line"
test "$(grep -c 'id-token: write' "$workflow")" -eq 1

test "$(wc -l < "$targets")" -eq 19
test -z "$(awk -F'|' 'NF != 3 || $1 == "" || $2 == "" || $3 == "" { print NR }' "$targets")"
test -z "$(cut -d'|' -f2 "$targets" | sort | uniq -d)"
test -z "$(cut -d'|' -f2 "$targets" | grep -Evi '^(com|de)\.[a-z0-9_.]+$' || true)"
test -z "$(cut -d'|' -f3 "$targets" | grep -Ev '^https://raw\.githubusercontent\.com/' || true)"

if cut -d'|' -f1-2 "$targets" | grep -Eqi 'navokids|maengelfix|idlehandwerker|rapportai'; then
  echo 'NavoKids, MängelFix, Idle Handwerker and Rapport AI must not be mutated by this batch.' >&2
  exit 1
fi

expected=$(mktemp)
actual=$(mktemp)
trap 'rm -f "$expected" "$actual"' EXIT

cat > "$expected" <<'EOF'
com.kamilunavo.kintaroq
com.kamilunavo.onemoretap
com.kamilunavo.schonerledigt
de.kamilunav.kaltecalc
de.kamilunavo.arbeitsklar
de.kamilunavo.brennercalc
de.kamilunavo.heizkorpercalc
de.kamilunavo.hydrocalc
de.kamilunavo.keepmeter
de.kamilunavo.luftungscalc
de.kamilunavo.magcalc
de.kamilunavo.navopass
de.kamilunavo.ninenine
de.kamilunavo.reklaio
de.kamilunavo.rohrcalc
de.kamilunavo.servicecheck
de.kamilunavo.volumecalc
de.kamilunavo.waermetakt
de.kamilunavo.zweicheck
EOF

cut -d'|' -f2 "$targets" | sort > "$actual"
diff -u "$expected" "$actual"

grep -q 'validate-play-icon-sources.sh' "$workflow"

echo 'Play icon sync contract passed.'
