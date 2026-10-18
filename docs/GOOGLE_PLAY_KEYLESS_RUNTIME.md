# Google Play verification runtime

The Android subscription verification route already exists, but the production container had no Google runtime credentials. The organization blocks service account key creation. Use a separate MaengelFix-only service account with X509 Workload Identity Federation; do not weaken that policy or reuse Kintaroq identity.

The server supports a read-only GOOGLE_APPLICATION_CREDENTIALS file and GOOGLE_CLOUD_PROJECT through google-auth-library. Existing valid GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_B64 configurations remain compatible. Neither credentials nor access tokens may be logged or bundled into Android. The existing account binding, entitlement delivery and RTDN verification remain unchanged. The Docker build-time RTDN patch accepts both authentication implementations.

The primary Compose file persists the runtime mount and three non-secret Google settings, so automatic Portainer Git deployments retain purchase verification. GOOGLE_PLAY_RUNTIME_DIR can override the production runtime directory on other hosts. The repository contains no certificate private keys or service-account keys.

Provision maengelfix-runtime/prod-x509 with the server CA public certificate. Restrict its subject to CN maengelfix-prod and URI spiffe://kamilunavo.com/maengelfix-prod, with only workloadIdentityUser on maengelfix-play-billing@emerald-caster-508318-f2.iam.gserviceaccount.com. Give that account finance/order access only to the MaengelFix app in Play Console. Mount only the leaf runtime folder; retain the CA private directory separately. Renew the one-year leaf certificate before expiry.

Before deployment preserve the existing database, upload volume, Apple and Stripe environment values and Compose service configuration. Back up the existing app image and database. Recreate only the app service. Verify actual read-only Google subscription catalog access and normal HTTP readiness. Never treat configuration inspection as an actual checkout test. Per the owner, do not repeat previously completed checkout tests.

Release candidate 1.0.6 (7) exposes the correct Google organization subscription SKUs and offers Business monthly only; the existing expensive Business annual Google plan stays inactive.

## Published Android compatibility

The actual production bundle 3 (1.0.2), SHA-256 8bed1149424e18b4d062d67f9a9d25952711a1e971330c119b7a74ea60d74ba8, contains the original com.kamilunavo.maengelfix.* product IDs and the complete existing workspace. The catalog instead contained only the newer maengelfix.* IDs. The unreleased native candidate 7 offers fewer workspace functions and must not replace production solely to repair billing.

Google rejects creation of these legacy identifiers as malformed; they cannot be mirrored into the modern catalog. No product was created or activated by the rejected attempt. A production-compatible Android patch is therefore required. It must retain the complete already published workspace and update its BillingClient integration to the existing valid maengelfix.* identifiers. Business remains monthly only. The limited unreleased native preview must not replace the current complete workspace as a side effect of this billing repair.

## Production-compatible release 8

Android 1.0.7 (8) retains the complete workspace implementation from the published 1.0.2 source instead of shipping the incomplete unreleased native preview. The workspace source is pinned by SHA-256 in CI. The current native BillingClient, product-account policy and monthly-only Business offer are retained. Its Google billing entry also works after single-page navigation; the Android billing view exposes only the native Google Play shop and never web Stripe checkout. Existing non-Android browser billing is unchanged.
