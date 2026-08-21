# MängelFix — Google Play release handoff

## Android identity

- App: MängelFix
- Package: `com.kamilunavo.maengelfix`
- Version: `1.0.0` (`versionCode 1`)
- Target SDK: Android 16 / API 36
- Minimum SDK: API 26
- Backend/web core: `https://maengelfix.kamilunavo.com`

## Android architecture

The Android app keeps the production MängelFix web/backend feature core for accounts, cases, photos, PDFs, deadlines and management, while Android-specific store/device functions stay native.

Native Android integration provides:

- persistent authenticated WebView session;
- HTTPS-only first-party navigation and deep links;
- native file/photo picker and authenticated DownloadManager;
- native Google Play subscription screen;
- Play Billing 9.1 product query, localized prices, purchase and restore;
- no server secrets embedded in the Android binary.

Stripe Checkout/Billing Portal remains blocked in the Play-distributed app both at the API request layer and for `stripe.com` navigation. Existing entitlements from another provider remain consumable after login, but Android will not start a duplicate Play subscription while an active Apple/Stripe/Play subscription already exists.

## Locked Google Play subscription catalog

| Plan | Period | Subscription ID | Base plan | DE price |
| --- | --- | --- | --- | ---: |
| Private Pro | Monthly | `com.kamilunavo.maengelfix.privatepro.monthly` | `monthly` | €4.99 |
| Private Pro | Yearly | `com.kamilunavo.maengelfix.privatepro.yearly` | `yearly` | €49.99 |
| Management Starter | Monthly | `com.kamilunavo.maengelfix.managementstarter.monthly` | `monthly` | €29.99 |
| Management Starter | Yearly | `com.kamilunavo.maengelfix.managementstarter.yearly` | `yearly` | €299.99 |
| Management Pro | Monthly | `com.kamilunavo.maengelfix.managementpro.monthly` | `monthly` | €59.99 |
| Management Pro | Yearly | `com.kamilunavo.maengelfix.managementpro.yearly` | `yearly` | €599.99 |
| Management Business | Monthly | `com.kamilunavo.maengelfix.managementbusiness.monthly` | `monthly` | €119.99 |
| Management Business | Yearly | `com.kamilunavo.maengelfix.managementbusiness.yearly` | `yearly` | €1,199.99 |

All eight are auto-renewing subscriptions. No introductory trial is required for the v1 Play launch.

### Server mapping

- `privatepro.*` → `private` / `private_pro`
- `managementstarter.*` → `organization` / `management_starter`
- `managementpro.*` → `organization` / `management_pro`
- `managementbusiness.*` → `organization` / `management_business`

## Purchase security path

Android does not unlock a plan from a client-supplied product ID.

1. Android reads the authenticated MängelFix account.
2. Before checkout it reads `/api/billing/plan`, blocks duplicate provider subscriptions, and rejects private/management scope mismatches.
3. The account UUID is SHA-256 hashed and supplied to Google as `obfuscatedAccountId`.
4. After Play reports `PURCHASED`, Android sends only product ID + purchase token to the authenticated MängelFix verification endpoint.
5. Server obtains its own Android Publisher OAuth token and calls Google Play `purchases.subscriptionsv2.get`.
6. Server uses the product and state returned by Google, compares Google's `obfuscatedExternalAccountId` with the authenticated account hash, and updates the mapped MängelFix entitlement.
7. Android acknowledges the purchase only after the MängelFix server has accepted the Google-verified purchase.

Purchase tokens are stored only as SHA-256 hashes in MängelFix subscription metadata. Google service-account credentials stay server-side.

## Lifecycle / RTDN

Endpoint:

`POST https://maengelfix.kamilunavo.com/api/billing/google-play/rtdn`

The endpoint accepts Google Pub/Sub authenticated push only. It validates:

- Google RS256 signature against Google's JWKS;
- issuer;
- configured OIDC audience;
- verified sender email;
- exact configured Pub/Sub push service account.

After authentication, RTDN data itself is not trusted for entitlement state. The server re-fetches the current subscription with `purchases.subscriptionsv2.get` and applies that state. Duplicate/out-of-order RTDN events are therefore safe because current Google state is authoritative.

Entitlement behavior:

- ACTIVE → access
- CANCELED but not expired → access until expiry
- IN_GRACE_PERIOD → access
- PENDING / ON_HOLD / EXPIRED → no active entitlement

A purchase RTDN can race the app's initial verify call. If the account-hash mapping does not exist yet, that first RTDN is acknowledged; the authenticated app verification establishes the mapping and current state. Later renewal/cancel/grace/hold RTDNs resolve through that mapping.

## Server deployment variables

Never commit real values.

- `GOOGLE_PLAY_PACKAGE_NAME=com.kamilunavo.maengelfix`
- `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_B64=<base64 service-account JSON>`
- `GOOGLE_PLAY_RTDN_AUDIENCE=https://maengelfix.kamilunavo.com/api/billing/google-play/rtdn`
- `GOOGLE_PLAY_RTDN_SERVICE_ACCOUNT_EMAIL=<Pub/Sub push service account>`

## Google Cloud / Play Console setup

1. Create/link the Google Cloud project used by the Play developer account.
2. Enable Android Publisher API access for the server service account and grant only the Play permissions required to read/manage MängelFix subscriptions.
3. Base64 the service-account JSON and place it only in the production deployment variable above.
4. Create all eight Play subscription records and activate `monthly` / `yearly` base plans with the locked launch prices.
5. Create a Pub/Sub topic for Google Play Real-time Developer Notifications and connect it in Play Console monetization settings.
6. Create a Pub/Sub push subscription to the RTDN endpoint above, enable authenticated push, select the dedicated push service account and set the exact audience value above.
7. Put that push service-account email into `GOOGLE_PLAY_RTDN_SERVICE_ACCOUNT_EMAIL` and redeploy.
8. Send a Play test notification and confirm HTTP 204.

## Suggested German Play listing

**Short description**  
Mängel dokumentieren, Beweise sammeln, Fristen verfolgen und PDFs erstellen.

MängelFix hilft privaten Nutzern und Hausverwaltungen, Mängel strukturiert zu erfassen, Fotos und Belege zuzuordnen, Fristen und Status zu verfolgen sowie professionelle PDF-Unterlagen zu erzeugen. Management-Tarife ergänzen Objekte, Einheiten, Teams, Aufgaben und Dienstleister. MängelFix ist ein Organisations- und Dokumentationstool und ersetzt keine Rechtsberatung.

## URLs

- Website: `https://maengelfix.kamilunavo.com`
- Support: `https://kamilunavo.com/support`
- Privacy: verify the current public MängelFix privacy URL immediately before Play submission.

## Release gates

- [x] API 36 Android project and native upload/download/deep-link integration.
- [x] Stripe checkout/portal blocked in Play-distributed Android app.
- [x] Native Play Billing 9.1 product query/purchase/restore UI.
- [x] Duplicate-provider and private/management scope checkout guards.
- [x] Authenticated server-side `subscriptionsv2` purchase-token verification.
- [x] Account binding through SHA-256 `obfuscatedAccountId`.
- [x] Server verification happens before purchase acknowledgement.
- [x] Authenticated Google OIDC RTDN lifecycle path.
- [x] Eight Android subscription IDs/prices/base plans locked.
- [ ] Current Android + server CI green after the billing/RTDN implementation.
- [ ] Configure service-account credentials in production and redeploy.
- [ ] Configure Play subscriptions/base plans.
- [ ] Configure Pub/Sub authenticated RTDN and pass the test notification.
- [ ] Build/sign the final post-billing AAB with the existing MängelFix upload key.
- [ ] Create/finish the Play Console app and Data safety/account deletion/content rating declarations.
- [ ] Internal test: login, case/photo/PDF flows, each relevant subscription, restore, pending purchase, cancellation, grace period, account hold/expiry and cross-device entitlement sync.
- [ ] Confirm Stripe checkout/portal remains unreachable from the Play build.
