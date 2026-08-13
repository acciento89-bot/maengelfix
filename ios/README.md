# MängelFix iOS

Native SwiftUI-App für iPhone und iPad. Sie verwendet dasselbe MängelFix-Konto und dasselbe Backend wie die Web-App unter `https://maengelfix.kamilunavo.com`.

## Stand v0.1

- Login und Registrierung
- bestehende Web-Session/Cookie-Authentifizierung
- Dashboard mit offenen/erledigten Vorgängen und Fristen
- Mängelliste mit Suche
- native Vorgangsdetailansicht mit Nachweisen und Verlauf
- neuen Mangel anlegen
- Tarif- und Profilanzeige
- Logout
- Universal Target für iPhone und iPad

## Projekt erzeugen

Das Xcode-Projekt wird mit XcodeGen aus `project.yml` generiert:

```bash
brew install xcodegen
cd ios
xcodegen generate
open MaengelFix.xcodeproj
```

Bundle Identifier: `com.kamilunavo.maengelfix`

## Signing

In Xcode beim Target `MaengelFix` unter **Signing & Capabilities** das eigene Apple Developer Team auswählen. Die Projektdatei enthält absichtlich keine persönlichen Signing-Zertifikate oder Secrets.

## CI

Der Workflow `.github/workflows/ios-ci.yml` generiert das Xcode-Projekt auf einem macOS-Runner und baut den iOS-Simulator ohne Code Signing. So werden Swift-/Xcode-Fehler bereits in GitHub erkannt.
