# Google Play verification runtime

The Android subscription verification route already exists, but the production container had no Google runtime credentials. The organization blocks service account key creation. Use a separate MaengelFix-only service account with X509 Workload Identity Federation; do not weaken that policy or reuse Kintaroq identity.

The server supports a read-only GOOGLE_APPLICATION_CREDENTIALS file and GOOGLE_CLOUD_PROJECT through google-auth-library. Existing valid GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_B64 configurations remain compatible. Neither credentials nor access tokens may be logged or bundled into Android. The existing account binding, entitlement delivery and RTDN verification remain unchanged. The Docker build-time RTDN patch accepts both authentication implementations.

Provision maengelfix-runtime/prod-x509 with the server CA public certificate. Restrict its subject to CN maengelfix-prod and URI spiffe://kamilunavo.com/maengelfix-prod, with only workloadIdentityUser on maengelfix-play-billing@emerald-caster-508318-f2.iam.gserviceaccount.com. Give that account finance/order access only to the MaengelFix app in Play Console. Mount only the leaf runtime folder; retain the CA private directory separately. Renew the one-year leaf certificate before expiry.

Before deployment preserve the existing database, upload volume, Apple and Stripe environment values and Compose service configuration. Back up the existing app image and database. Recreate only the app service. Verify actual read-only Google subscription catalog access and normal HTTP readiness. Never treat configuration inspection as an actual checkout test. Per the owner, do not repeat previously completed checkout tests.

Release candidate 1.0.6 (7) exposes the correct Google organization subscription SKUs and offers Business monthly only; the existing expensive Business annual Google plan stays inactive.
