#!/usr/bin/env bash
set -euo pipefail

: "${PACKAGE_NAME:?PACKAGE_NAME is required}"
: "${APK_PATH:?APK_PATH is required}"
: "${OUTPUT_DIR:?OUTPUT_DIR is required}"
: "${SECOND_ACTION:?SECOND_ACTION is required}"

readonly apk_path="$GITHUB_WORKSPACE/$APK_PATH"
readonly output_dir="$GITHUB_WORKSPACE/$OUTPUT_DIR"

wait_for_foreground() {
  local attempt
  for attempt in $(seq 1 45); do
    if adb shell dumpsys window |
      grep -E "mCurrentFocus|mFocusedApp" |
      grep -Fq "$PACKAGE_NAME"; then
      return 0
    fi
    sleep 1
  done
  echo "Timed out waiting for $PACKAGE_NAME to become the foreground app." >&2
  adb shell dumpsys window |
    grep -E "mCurrentFocus|mFocusedApp" >&2 || true
  return 1
}

launch_app() {
  adb shell am force-stop "$PACKAGE_NAME"
  adb shell monkey -p "$PACKAGE_NAME" -c android.intent.category.LAUNCHER 1
  wait_for_foreground
  sleep 10
}

assert_clean_foreground() {
  if ! adb shell dumpsys window |
    grep -E "mCurrentFocus|mFocusedApp" |
    grep -Fq "$PACKAGE_NAME"; then
    echo "Expected $PACKAGE_NAME in the foreground; refusing to capture." >&2
    adb shell dumpsys window |
      grep -E "mCurrentFocus|mFocusedApp" >&2 || true
    return 1
  fi
}

mkdir -p "$output_dir"
rm -f "$output_dir"/*.png
test -s "$apk_path"
adb install -r "$apk_path"
adb shell settings put system accelerometer_rotation 0
adb shell settings put system user_rotation 0
adb shell cmd locale set-app-locales "$PACKAGE_NAME" --user 0 de-DE || true

launch_app
assert_clean_foreground
adb exec-out screencap -p > "$output_dir/01-current-ui.png"

case "$SECOND_ACTION" in
  tap)
    adb shell input tap "${TAP_X:-540}" "${TAP_Y:-1900}"
    sleep 4
    ;;
  swipe)
    adb shell input swipe 540 1900 540 650 600
    sleep 4
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

assert_clean_foreground
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
