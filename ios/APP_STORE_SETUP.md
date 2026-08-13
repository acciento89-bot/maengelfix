# MängelFix – App Store / TestFlight Setup

## App
- Plattform: iOS (iPhone + iPad)
- Name: MängelFix
- Bundle ID: `com.kamilunavo.maengelfix`
- SKU: `maengelfix-ios-001`
- Primärsprache: Deutsch
- Version: `0.3.0`

## Auto-Renewable Subscriptions
Subscription Group: `MängelFix Privat Pro`

### Monatlich
- Reference Name: `MängelFix Privat Pro Monat`
- Product ID: `com.kamilunavo.maengelfix.privatepro.monthly`
- Duration: 1 month
- Zielpreis DE: 4,99 €

### Jährlich
- Reference Name: `MängelFix Privat Pro Jahr`
- Product ID: `com.kamilunavo.maengelfix.privatepro.yearly`
- Duration: 1 year
- Zielpreis DE: 49,99 €

## App Store Server Notifications
Production URL und Sandbox URL:

`https://maengelfix.kamilunavo.com/api/billing/apple/notifications`

## Server-Umgebungsvariablen
Diese Werte kommen aus App Store Connect > Users and Access > Integrations > In-App Purchase.

```env
APPLE_APP_BUNDLE_ID=com.kamilunavo.maengelfix
APPLE_IAP_ISSUER_ID=<Issuer ID>
APPLE_IAP_KEY_ID=<Key ID>
APPLE_IAP_PRIVATE_KEY=<Inhalt der .p8-Datei; bei einzeiliger ENV mit \\n als Zeilenumbruch>
```

Der private `.p8`-Schlüssel darf niemals in GitHub eingecheckt werden.

## URLs für Metadaten
- Marketing-/Produktseite: `https://maengelfix.kamilunavo.com`
- Datenschutz: `https://maengelfix.kamilunavo.com/datenschutz`
- Nutzungsbedingungen: `https://maengelfix.kamilunavo.com/nutzungsbedingungen`

## Deutsche Store-Texte (Entwurf)

**Untertitel**
`Mängel sauber dokumentieren`

**Beschreibung**
MängelFix bündelt deine Mängelmeldungen an einem Ort. Dokumentiere Schäden und Probleme mit Beschreibung, Fotos, Datum, Empfänger und Frist. Erstelle übersichtliche PDFs, behalte den Verlauf im Blick und ergänze Nachweise direkt unterwegs.

Ob Wohnung, Lieferung, Produkt, Fahrzeug, Dienstleistung oder Reise: Jeder Mangel bleibt als eigener Vorgang nachvollziehbar. Für digital verbundene Mietervorgänge können Nachrichten direkt mit der Verwaltung ausgetauscht werden.

Privat Pro erweitert MängelFix unter anderem um zusätzliche Nachweise, Fristen und weitere Organisationsfunktionen.

MängelFix ist ein Organisations- und Dokumentationstool und ersetzt keine Rechtsberatung.

**Keywords**
`Mängel,Schaden,Dokumentation,Fotos,Frist,PDF,Wohnung,Reklamation`

**Review-Hinweis**
Die App verwendet dasselbe MängelFix-Konto wie die Webanwendung. Bestehende Nutzer können sich anmelden. Privat Pro kann in der iOS-App über Apples In-App Purchase erworben werden; bereits außerhalb der App bestehende Berechtigungen werden nach Anmeldung ebenfalls erkannt.
