#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

ARCHIVE="/tmp/MaengelFix-AppStore.xcarchive"
DERIVED="/tmp/MaengelFix-TestFlightBuild"
LOG="/tmp/maengelfix-testflight-build.log"
APP="$ARCHIVE/Products/Applications/MaengelFix.app"
INFO="$APP/Info.plist"

printf '\n=== MÄNGELFIX TESTFLIGHT BUILD ===\n'
command -v xcodegen >/dev/null || { echo 'FEHLER: xcodegen nicht installiert.'; exit 1; }

printf '\n=== 1. XCODE-PROJEKT ERZEUGEN ===\n'
xcodegen generate

printf '\n=== 2. RELEASE BUILD OHNE SIGNING ===\n'
rm -rf "$DERIVED"
rm -f "$LOG"
set +e
xcodebuild \
  -project MaengelFix.xcodeproj \
  -scheme MaengelFix \
  -configuration Release \
  -sdk iphoneos \
  -derivedDataPath "$DERIVED" \
  CODE_SIGNING_ALLOWED=NO \
  build >"$LOG" 2>&1
STATUS=$?
set -e
if [ "$STATUS" -ne 0 ]; then
  echo 'FEHLER: Release-Build fehlgeschlagen.'
  grep -n -B5 -A12 -E 'error:|com.apple.actool.errors' "$LOG" | tail -120 || true
  exit 1
fi
echo 'OK: Release-Build erfolgreich.'

printf '\n=== 3. ARCHIVE BUILD 7 ===\n'
rm -rf "$ARCHIVE"
xcodebuild \
  -project MaengelFix.xcodeproj \
  -scheme MaengelFix \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath "$ARCHIVE" \
  archive

[ -f "$INFO" ] || { echo 'FEHLER: Archivierte Info.plist fehlt.'; exit 1; }

VERSION=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$INFO")
BUILD=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$INFO")
ICON=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIcons:CFBundlePrimaryIcon:CFBundleIconName' "$INFO" 2>/dev/null || true)
ENCRYPTION=$(/usr/libexec/PlistBuddy -c 'Print :ITSAppUsesNonExemptEncryption' "$INFO" 2>/dev/null || true)

printf '\n=== 4. PREFLIGHT ===\n'
echo "Version: $VERSION"
echo "Build:   $BUILD"
echo "Icon:    $ICON"
echo "Non-exempt encryption: $ENCRYPTION"

[ "$VERSION" = "0.4.0" ] || { echo 'FEHLER: Falsche Marketing-Version.'; exit 1; }
[ "$BUILD" = "7" ] || { echo 'FEHLER: Es wurde nicht Build 7 archiviert.'; exit 1; }
[ "$ICON" = "AppIcon" ] || { echo 'FEHLER: AppIcon fehlt im Archiv.'; exit 1; }
[ "$ENCRYPTION" = "false" ] || [ "$ENCRYPTION" = "NO" ] || { echo 'FEHLER: Export-Compliance-Key fehlt.'; exit 1; }

/usr/libexec/PlistBuddy -c 'Print :UISupportedInterfaceOrientations' "$INFO" >/dev/null
/usr/libexec/PlistBuddy -c 'Print :UISupportedInterfaceOrientations~ipad' "$INFO" >/dev/null

codesign --verify --deep --strict --verbose=2 "$APP"
SIGNING=$(codesign -dvv "$APP" 2>&1 || true)
echo "$SIGNING" | grep -q 'Authority=Apple Distribution:' || { echo 'FEHLER: Archiv ist nicht mit Apple Distribution signiert.'; exit 1; }
echo "$SIGNING" | grep -q 'TeamIdentifier=TKG684N5GL' || { echo 'FEHLER: Falsches Signing-Team.'; exit 1; }

PROFILE_PLIST="/tmp/maengelfix-embedded-profile.plist"
security cms -D -i "$APP/embedded.mobileprovision" > "$PROFILE_PLIST"
PROFILE_NAME=$(/usr/libexec/PlistBuddy -c 'Print :Name' "$PROFILE_PLIST")
GET_TASK_ALLOW=$(/usr/libexec/PlistBuddy -c 'Print :Entitlements:get-task-allow' "$PROFILE_PLIST" 2>/dev/null || true)
echo "Profile: $PROFILE_NAME"
echo "get-task-allow: $GET_TASK_ALLOW"
[ "$PROFILE_NAME" = "MaengelFix App Store" ] || { echo 'FEHLER: Falsches Provisioning Profile.'; exit 1; }
[ "$GET_TASK_ALLOW" = "false" ] || [ "$GET_TASK_ALLOW" = "NO" ] || { echo 'FEHLER: Development-Entitlement im App-Store-Archiv.'; exit 1; }

echo 'OK: Preflight vollständig bestanden.'

printf '\n=== 5. UPLOAD ZU APP STORE CONNECT ===\n'
xcodebuild \
  -exportArchive \
  -archivePath "$ARCHIVE" \
  -exportOptionsPlist ExportOptions.plist \
  -allowProvisioningUpdates

printf '\n=====================================\n'
echo 'MÄNGELFIX BUILD 7 WURDE AN APP STORE CONNECT ÜBERGEBEN.'
echo 'Nach der Verarbeitung in TestFlight installieren und Privat Pro + Verwaltung testen.'
echo '====================================='
