# Google Play verification runtime

The Android subscription verification route already exists, but the production container had no Google runtime credentials. The organization blocks service account key creation. Use a separate MaengelFix-only service account with X509 Workload Identity Federation; do not weaken that policy or reuse Kintaroq identity.

The server supports a read-only GOOGLE_APPLICATION_CREDENTIALS file and GOOGLE_CLOUD_PROJECT through google-auth-library. Existing valid GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_B64 configurations remain compatible. Neither credentials nor access tokens may be logged or bundled into Android. The existing account binding, entitlement delivery and RTDN verification remain unchanged. The Docker build-time RTDN patch accepts both authentication implementations.

The primary Compose file persists the runtime mount and three non-secret Google settings, so automatic Portainer Git deployments retain purchase verification. GOOGLE_PLAY_RUNTIME_DIR can override the production runtime directory on other hosts. The repository contains no certificate private keys or service-account keys.

Provision maengelfix-runtime/prod-x509 with the server CA public certificate. Restrict its subject to CN maengelfix-prod and URI spiffe://kamilunavo.com/maengelfix-prod, with only workloadIdentityUser on maengelfix-play-billing@emerald-caster-508318-f2.iam.gserviceaccount.com. Give that account finance/order access only to the MaengelFix app in Play Console. Mount only the leaf runtime folder; retain the CA private directory separately. Renew the one-year leaf certificate before expiry.

Before deployment preserve the existing database, upload volume, Apple and Stripe environment values and Compose service configuration. Back up the existing app image and database. Recreate only the app service. Verify actual read-only Google subscription catalog access and normal HTTP readiness. Never treat configuration inspection as an actual checkout test. Per the owner, do not repeat previously completed checkout tests.

Release candidate 1.0.6 (7) exposes the correct Google organization subscription SKUs and offers Business monthly only; the existing expensive Business annual Google plan stays inactive.

## Published Android compatibility

The actual production bundle 3 (1.0.2), SHA-256 8bed1149424e18b4d062d67f9a9d25952711a1e971330c119b7a74ea60d74ba8, contains the original com.kamilunavo.maengelfix.* product IDs and the complete existing workspace. The catalog instead contained only the newer maengelfix.* IDs. The unreleased native candidate 7 offers fewer workspace functions and must not replace production solely to repair billing.

Seven legacy product identifiers are therefore mapped to the same verified server plans and populated in Google Play by copying the existing matching product prices, billing periods and regional availability. The current products stay intact for future native clients. Legacy Business annual is deliberately not offered. All verification still comes from Google with the existing account binding and cross-provider double-subscription guard. This does not create two subscriptions for any customer; only an explicit subsequent checkout could subscribe, and already active accounts are blocked from starting another subscription.

The manual catalog workflow defaults to audit. Apply only mirrors the seven allowlisted products and activates their corresponding base plans; it never modifies originals, redeems codes or creates a purchase. Runtime application credentials retain app-specific read/order access, while the existing authorized operations identity performs catalog maintenance.
