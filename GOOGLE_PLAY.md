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

MängelFix currently has server-side Stripe subscriptions and Apple In-App Purchase subscriptions. The Android release MUST NOT initiate Stripe Checkout or Stripe Billing Portal from inside the Play-distributed app.

The Android client therefore has two independent guards:

1. requests to `/api/billing/checkout` and `/api/billing/portal` are blocked inside the WebView;
2. navigation to `stripe.com` and all `.stripe.com` subdomains is blocked.

The billing page also hides external checkout/portal buttons and explains that new Android digital subscriptions will be offered through Google Play.

Existing server-side entitlements remain consumable after sign-in. Free accounts keep the current Free feature set.

Google Play subscriptions must not be enabled in the Android UI until server-side Google Play purchase-token verification is green end-to-end. Do not remove the Stripe guards after Play Billing is added; the Play-distributed client must continue to route new Android digital purchases through Google Play.

## Locked Google Play subscription catalog

To keep Android product-to-plan mapping identical to the existing Apple/server mapping, Google Play uses the same eight product identifiers. They are independent store records even though the identifiers match.

| Plan | Billing period | Google Play subscription ID | Base plan ID | Germany price |
| --- | --- | --- | --- | ---: |
| Private Pro | Monthly | `com.kamilunavo.maengelfix.privatepro.monthly` | `monthly` | €4.99 |
| Private Pro | Yearly | `com.kamilunavo.maengelfix.privatepro.yearly` | `yearly` | €49.99 |
| Management Starter | Monthly | `com.kamilunavo.maengelfix.managementstarter.monthly` | `monthly` | €29.99 |
| Management Starter | Yearly | `com.kamilunavo.maengelfix.managementstarter.yearly` | `yearly` | €299.99 |
| Management Pro | Monthly | `com.kamilunavo.maengelfix.managementpro.monthly` | `monthly` | €59.99 |
| Management Pro | Yearly | `com.kamilunavo.maengelfix.managementpro.yearly` | `yearly` | €599.99 |
| Management Business | Monthly | `com.kamilunavo.maengelfix.managementbusiness.monthly` | `monthly` | €119.99 |
| Management Business | Yearly | `com.kamilunavo.maengelfix.managementbusiness.yearly` | `yearly` | €1,199.99 |

Configuration rule for all eight:

- type: subscription;
- renewal: auto-renewing;
- no introductory trial required for v1;
- activate the base plan only after the matching server verification path exists;
- configure desired countries/regions and let Play calculate local prices from the locked EUR launch price unless a market-specific decision overrides it later.

### Server plan mapping

- `privatepro.*` → scope `private`, plan `private_pro`
- `managementstarter.*` → scope `organization`, plan `management_starter`
- `managementpro.*` → scope `organization`, plan `management_pro`
- `managementbusiness.*` → scope `organization`, plan `management_business`

Server verification must validate at minimum:

- Android package is exactly `com.kamilunavo.maengelfix`;
- product ID is one of the eight IDs above;
- purchase token is valid at Google Play;
- purchase/account association belongs to the authenticated MängelFix account;
- expiry, cancellation, grace-period/account-hold and replacement/upgrade state are honored;
- a client-supplied product or plan value is never trusted without Play verification;
- Google service-account credentials remain server-side only.

## Existing server plan catalog

- `private_free`: €0
- `private_pro`: €4.99 monthly / €49.99 yearly
- `management_starter`: €29.99 monthly / €299.99 yearly
- `management_pro`: €59.99 monthly / €599.99 yearly
- `management_business`: €119.99 monthly / €1,199.99 yearly

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
- [x] Android CI tests + debug bundle + minified release bundle green.
- [x] Signed upload AAB generated with a private RSA-4096 upload key.
- [x] Eight Android subscription IDs/prices/base-plan IDs locked in this handoff.
- [ ] Implement BillingClient subscription UI/query/purchase/restore.
- [ ] Implement authenticated server-side Google Play purchase-token verification.
- [ ] Add Google Play lifecycle handling before production (expiry/cancel/grace/account hold; RTDN recommended).
- [ ] Create Play Console app with package `com.kamilunavo.maengelfix`.
- [ ] Create the eight subscription records, but do not expose purchases until server verification is green.
- [ ] Complete Data safety against the production backend data flows.
- [ ] Complete account deletion declaration and provide the existing deletion path/URL.
- [ ] Complete target audience/content rating.
- [ ] Internal test: registration/login, existing login, create/edit case, photo upload, PDF download, logout/relogin, existing Pro entitlement.
- [ ] Verify no Stripe checkout/portal can be reached from Android.
- [ ] Internal billing test: each relevant plan/cadence, restore, cancellation/expiry and cross-device entitlement sync.
