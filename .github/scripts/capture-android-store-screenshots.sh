#!/usr/bin/env bash
set -euo pipefail

: "${PACKAGE_NAME:?PACKAGE_NAME is required}"
: "${APK_PATH:?APK_PATH is required}"
: "${OUTPUT_DIR:?OUTPUT_DIR is required}"
: "${WAIT_TEXT:?WAIT_TEXT is required}"
: "${SECOND_ACTION:?SECOND_ACTION is required}"

readonly apk_path="$GITHUB_WORKSPACE/$APK_PATH"
readonly output_dir="$GITHUB_WORKSPACE/$OUTPUT_DIR"

current_focus() {
  adb shell dumpsys window | grep "mCurrentFocus" | head -n 1 || true
}

hide_error_dialogs() {
  adb shell settings put global hide_error_dialogs 1 || true
  adb shell settings put global anr_show_background 0 || true
  adb shell am broadcast -a android.intent.action.CLOSE_SYSTEM_DIALOGS >/dev/null 2>&1 || true
}

assert_no_system_dialog() {
  local focus
  focus="$(current_focus)"
  if [[ "$focus" != *"$PACKAGE_NAME"* ]]; then
    echo "Unexpected foreground window; refusing to capture: $focus" >&2
    return 1
  fi
}

wait_for_foreground() {
  local attempt
  for attempt in $(seq 1 45); do
    if [[ "$(current_focus)" == *"$PACKAGE_NAME"* ]]; then
      return 0
    fi
    hide_error_dialogs
    sleep 1
  done
  echo "Timed out waiting for $PACKAGE_NAME to become the foreground app." >&2
  current_focus >&2
  return 1
}

wait_for_ui_text() {
  local expected="$1"
  local attempt
  for attempt in $(seq 1 45); do
    if adb exec-out uiautomator dump /dev/tty 2>/dev/null | grep -Fq "$expected"; then
      return 0
    fi
    assert_no_system_dialog
    sleep 1
  done
  echo "Timed out waiting for visible app text: $expected" >&2
  adb exec-out uiautomator dump /dev/tty >&2 || true
  return 1
}

launch_app() {
  adb shell am force-stop "$PACKAGE_NAME"
  hide_error_dialogs
  adb shell am start -W -n "$PACKAGE_NAME/.MainActivity"
  wait_for_foreground
  wait_for_ui_text "$WAIT_TEXT"
  assert_no_system_dialog
}

tap_by_text() {
  local label="$1"
  local coordinates
  adb shell uiautomator dump /sdcard/window.xml >/dev/null
  coordinates="$(adb exec-out cat /sdcard/window.xml | python3 -c 'import re,sys; label=sys.argv[1]; data=sys.stdin.read(); node=next((n for n in re.findall(r"<node [^>]+>", data) if f"text=\"{label}\"" in n), None); assert node, f"Visible text not found: {label}"; x1,y1,x2,y2=map(int,re.search(r"bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"",node).groups()); print((x1+x2)//2,(y1+y2)//2)' "$label")"
  read -r tap_x tap_y <<<"$coordinates"
  adb shell input tap "$tap_x" "$tap_y"
}

mkdir -p "$output_dir"
rm -f "$output_dir"/*.png
test -s "$apk_path"
adb install -r "$apk_path"
adb shell settings put system accelerometer_rotation 0
adb shell settings put system user_rotation 0
adb shell cmd locale set-app-locales "$PACKAGE_NAME" --user 0 de-DE || true

launch_app
adb exec-out screencap -p > "$output_dir/01-current-ui.png"

case "$SECOND_ACTION" in
  tap)
    : "${SECOND_TEXT:?SECOND_TEXT is required for tap}"
    tap_by_text "$SECOND_TEXT"
    ;;
  swipe)
    adb shell input swipe 540 1900 540 650 600
    ;;
  dark)
    adb shell cmd uimode night yes
    launch_app
    ;;
  *)
    echo "Unsupported SECOND_ACTION: $SECOND_ACTION" >&2
    exit 1
    ;;
esac

if [[ "$SECOND_ACTION" != dark ]]; then
  wait_for_foreground
  wait_for_ui_text "${SECOND_WAIT_TEXT:-$WAIT_TEXT}"
fi
assert_no_system_dialog
adb exec-out screencap -p > "$output_dir/02-current-ui-detail.png"

python3 - "$output_dir" <<'PY'
import hashlib
import struct
import sys
from pathlib import Path

paths = sorted(Path(sys.argv[1]).glob('*.png'))
assert len(paths) == 2, paths
digests = set()
for path in paths:
    data = path.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', path
    width, height = struct.unpack('>II', data[16:24])
    assert (width, height) == (1080, 2400), (path, width, height)
    digests.add(hashlib.sha256(data).hexdigest())
assert len(digests) == 2, 'Screenshots must show two distinct real app states'
PY
