# MängelFix — Google Play release handoff

## Android identity

- App: MängelFix
- Package: `com.kamilunavo.maengelfix`
- Version: `1.0.0` (`versionCode 1`)
- Target SDK: Android 16 / API 36
- Minimum SDK: API 26
- Category: Productivity / Tools
- Backend/web core: `https://maengelfix.kamilunavo.com`

## Android architecture

The Android client intentionally reuses the production MängelFix web/backend application so the account, case, photo, PDF, deadline, team and management feature set does not fork from the existing service.

Native Android integration provides:

- persistent authenticated WebView session;
- HTTPS-only first-party navigation;
- Android deep links for the MängelFix domain;
- native file/photo picker for evidence uploads;
- authenticated native DownloadManager handling for generated PDFs/files;
- offline/main-frame error state and retry;
- back navigation integrated with Android;
- external links opened outside the app;
- no secrets embedded in the Android binary.

## Google Play payments policy guard

MängelFix currently has server-side Stripe subscriptions and Apple In-App Purchase subscriptions. The first Android release MUST NOT initiate Stripe Checkout or Stripe Billing Portal from inside the Play-distributed app.

The Android client therefore has two independent guards:

1. requests to `/api/billing/checkout` and `/api/billing/portal` are blocked inside the WebView;
2. navigation to Stripe hosts is blocked.

The billing page also hides external checkout/portal buttons and explains that new Android digital subscriptions will be offered through Google Play.

Existing server-side entitlements remain consumable after sign-in. Free accounts keep the current Free feature set.

A future Play Billing subscription implementation requires server-side Google Play purchase-token verification before Android can sell Pro/Management plans. Do not remove the Stripe guards until that integration is verified end-to-end.

## Existing server plan catalog

Current server catalog:

- `private_free`: €0
- `private_pro`: €4.99 monthly / €49.99 yearly
- `management_starter`: €29.99 monthly / €299.99 yearly
- `management_pro`: €59.99 monthly / €599.99 yearly
- `management_business`: €119.99 monthly / €1199.99 yearly

Existing Apple identifiers are platform-specific billing records and are not proof of Google Play product setup.

## Suggested German Play listing

### Short description
Mängel dokumentieren, Beweise sammeln, Fristen verfolgen und PDFs erstellen.

### Full description
MängelFix hilft dir, Mängel strukturiert zu dokumentieren und den gesamten Vorgang nachvollziehbar an einem Ort zu organisieren.

Für private Nutzer:
- Mängel zu Wohnung, Lieferung, Produkt, Werkstatt, Reise oder Dienstleistung erfassen
- Fotos und Belege dem Vorgang zuordnen
- Empfänger und Referenzen hinterlegen
- Fristen und Status im Blick behalten
- professionelle PDF-Unterlagen erzeugen und herunterladen
- Verlauf sauber dokumentieren

Für Hausverwaltungen:
- Objekte und Einheiten organisieren
- Mängelmeldungen strukturiert bearbeiten
- Team, Zuständigkeiten und Dienstleister koordinieren
- Aufgaben, Termine und Fristen verwalten
- Arbeitsaufträge und Übergabeinformationen dokumentieren

MängelFix ist ein Organisations- und Dokumentationstool und ersetzt keine Rechtsberatung.

## URLs

- Website: `https://maengelfix.kamilunavo.com`
- Support: `https://kamilunavo.com/support`
- Privacy: use the current public MängelFix privacy URL from the production website/Play Console setup.

## Release gates

- [x] Android API 36 project created.
- [x] Native upload/download/deep-link integration.
- [x] Stripe checkout/portal blocked in Play-distributed Android app.
- [ ] Android CI debug + release bundle green.
- [ ] Signed upload AAB generated with a private upload key.
- [ ] Create Play Console app with package `com.kamilunavo.maengelfix`.
- [ ] Complete Data safety against the production backend data flows.
- [ ] Complete account deletion declaration and provide the existing deletion path/URL.
- [ ] Complete target audience/content rating.
- [ ] Internal test: registration/login, existing login, create/edit case, photo upload, PDF download, logout/relogin, existing Pro entitlement.
- [ ] Verify no Stripe checkout/portal can be reached from Android.
- [ ] Add Google Play Billing + server verification before selling Android subscriptions.
