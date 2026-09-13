# Kamilunavo Android / iOS Parity Overhaul

Stand: 2026-09-13

## Verbindliche Regeln

- NavoKids ist ausdrücklich ausgenommen und bleibt unverändert.
- iOS ist pro Produkt die visuelle und funktionale Referenz, sofern keine gemeinsame Cross-Platform-Codebasis bereits dieselbe UI liefert.
- Android darf plattformtypische Systemdialoge und Navigation nutzen, aber Produktstruktur, Funktionen, Inhalte, Farben, Karten, Hierarchie und Monetarisierung müssen dem iOS-Produkt entsprechen.
- Keine Veröffentlichung mit erfundenen oder veralteten Screenshots. Play-Screenshots stammen aus exakt dem getesteten Android-Build.
- Launcher-/Startsymbol und Play-Store-Symbol müssen identisch sein und werden per CI geprüft.
- Systemleisten werden pro App explizit behandelt: korrekte Statusbar-Icon-Helligkeit, transparente/markenkonforme Fläche, `WindowInsets.safeDrawing` bzw. saubere Safe-Area-Nutzung und keine doppelte Statusbar-Padding-Kette.
- Bestehende Play-Einträge werden nur ersetzt/gelöscht, wenn ein Update des vorhandenen Pakets technisch oder produktseitig schlechter wäre. Ein UI-Framework-Wechsel allein ist kein Grund für einen neuen Store-Eintrag.
- Keine Production-Freigabe, solange Billing, Funktionsparität, Screenshots oder Signierung nicht verifiziert sind.

## Apps

| App | Repository | Android-Basis | Status | Schwerpunkt |
| --- | --- | --- | --- | --- |
| NavoKids | `navokids` | Expo/React Native | EXCLUDED / OK | Keine Änderung |
| Kintaroq | `kamilunavo/android/Kintaroq` | Legacy Android -> Jetpack Compose | IN PROGRESS | Vollständiger Neuaufbau nach SwiftUI inkl. Diagnose, Fälle, Scanner/OCR, Rescue, FaultLab, FixProof, Repairability, Billing |
| ZweiCheck | `zweicheck` | Jetpack Compose | TODO AUDIT | iOS-Screen-/Feature-Parität, Systemleisten, Billing, echte Screenshots |
| ArbeitsKlar | `arbeitsklar` | Jetpack Compose | TODO AUDIT | iOS-Screen-/Feature-Parität, Systemleisten, Billing, echte Screenshots |
| WärmeTakt | `w-rmetakt` | Expo/React Native | TODO AUDIT | gemeinsame UI prüfen, Android Safe Area/Statusbar, Billing, Screenshots |
| Reklaio | `reklaio` | Expo/React Native | TODO AUDIT | gemeinsame UI prüfen, Android Safe Area/Statusbar, Billing, Screenshots |
| MängelFix | `maengelfix` | Jetpack Compose | TODO AUDIT | iOS-/Produktparität, Systemleisten, Billing, Screenshots |
| NavoPass | `navopass` | Jetpack Compose | TODO AUDIT | iOS-Parität, Systemleisten, Navigation, Screenshots |
| 99,9 % | `99-9` | zu prüfen | TODO AUDIT | vollständige Android-/iOS-Parität, Icon/Store-Assets |
| NavoTap | `onemoretap` | Jetpack Compose | TODO AUDIT | iOS-Parität, Tipp-Erkennung, Systemleisten, Screenshots |
| KälteCalc | `SHK` | Jetpack Compose Flavor | TODO AUDIT | iOS-Parität, Statusbar, Store-Preis, Screenshots |
| LüftungsCalc | `SHK` | Jetpack Compose Flavor | TODO AUDIT | iOS-Parität, Statusbar, Store-Preis, Screenshots |
| HeizkörperCalc | `SHK` | Jetpack Compose Flavor | TODO AUDIT | iOS-Parität, Statusbar, Store-Preis, Screenshots |
| RohrCalc | `SHK` | Jetpack Compose Flavor | TODO AUDIT | iOS-Parität, Statusbar, Upload-Key-Reset, Screenshots |
| AnlagenCheck | `SHK` | Jetpack Compose Flavor | TODO AUDIT | iOS-Parität, Statusbar, Screenshots |
| VolumeCalc | `AnlagenVolumen` | Jetpack Compose | TODO AUDIT | iOS-Parität, Top-/Statusbar, Kontrast, Screenshots |
| KeepMeter | `keepmeter` | Jetpack Compose | TODO AUDIT | iOS-Parität, Inset-Dopplung prüfen, Screenshots |
| Schon erledigt? | `schonerledigt` | Jetpack Compose | TODO AUDIT | iOS-Parität, Systemleisten, Billing, Screenshots |
| BrennerCalc | `BrennerCalc` | Jetpack Compose | TODO AUDIT | iOS-Parität, Systemleisten, Billing/Preis, Screenshots |
| HydroCalc | `HydroCalc` | Jetpack Compose | TODO AUDIT | iOS-Parität, Systemleisten, Billing/Preis, Screenshots |
| MAGCalc | `MAGCalc` | Jetpack Compose | TODO AUDIT | iOS-Parität, Systemleisten, Icon/Store-Assets, Screenshots |

## Definition of Done pro App

1. iOS-/Referenz-Screens und Funktionen inventarisiert.
2. Android-Screens und Funktionen 1:1 gegen Inventar abgeglichen.
3. Fehlende oder abweichende UI/Funktionen umgesetzt.
4. Statusbar, Navigationbar, Safe Area und Tastaturverhalten auf Android geprüft.
5. DE/EN vollständig und ohne Mischsprache.
6. Billing/Preis/Restore bzw. Einmalkauf technisch getestet, sofern vorhanden.
7. Launcher-Icon == Play-Icon per CI-Guard.
8. Debug-/Internal-Test-Build erfolgreich.
9. Echte DE/EN-Screenshots aus dem finalen Android-Build erzeugt.
10. Erst danach AAB signieren und zur Prüfung/Production weitergeben.

## Systemleisten-Standard

### Jetpack Compose

- `enableEdgeToEdge(...)` mit zum Hintergrund passender `SystemBarStyle`.
- Ein einziges Inset-Konzept pro Screen: bevorzugt `Scaffold(contentWindowInsets = WindowInsets.safeDrawing)` oder bewusst gesetztes `windowInsetsPadding`.
- Keine Kombination aus `safeDrawing` + zusätzlichem `statusBarsPadding()` auf derselben Hierarchie ohne begründeten Bedarf.
- App-Inhalt darf nicht unter Netzbetreiber/Uhr/Akku oder Gestennavigation liegen.

### Expo / React Native

- explizite `StatusBar`-Konfiguration pro Theme.
- Safe-Area-Werte für Top/Bottom verwenden; keine hart codierten Statusbar-Höhen.
- Navigation Bar und Splash/Launcher-Farbe an die tatsächliche App-Oberfläche angleichen.

## Aktiver erster Umbau

Kintaroq: Draft-PR `#59` in `acciento89-bot/kamilunavo` auf Branch `fix/kintaroq-android-ios-parity`. Keine Production-Freigabe vor grünem Build, visueller Screenshot-Prüfung und vollständiger Google-Play-Purchase-Verifikation.
