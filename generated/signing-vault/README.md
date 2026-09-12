# Kamilunavo Android signing vault

This directory contains **ciphertext only**. It is safe to keep in the repository because the vault passphrase is wrapped with a Google Cloud KMS asymmetric key whose private key never leaves Cloud KMS.

## Integrity

- Vault encoding: Base64 split across `android-signing-bundle.enc.part00` through `part07`.
- Decoded encrypted-vault SHA-256: `5d8d06ea9c7a654b9037701f9b63ff20f25f017c140fbea4f28c439898bef3e8`.
- Wrapped-passphrase SHA-256: `6d6c0ae4b5c86f59195c20b9d84d413dbaa2efa19d7e57c26aec22fc18a55d49`.
- Cipher: AES-256-CBC with PBKDF2, 600000 iterations.
- KMS project: `emerald-caster-508318-f2`.
- KMS location/keyring/key/version: `global/kamilunavo-signing/android-upload-key-wrap/1`.

The wrapping public key is published at `generated/signing-bridge-public.pem`. The private key is non-exportable from Cloud KMS.

## Runtime use

Use `.github/actions/restore-android-signing/action.yml`. The action authenticates by GitHub OIDC/WIF, verifies both ciphertext checksums, asks Cloud KMS to unwrap the random vault passphrase, decrypts the vault inside `RUNNER_TEMP`, selects the requested application entry, masks all credentials, and exports the selected keystore path/credentials through `GITHUB_ENV` for the remainder of the job.

No plaintext keystore, store password, key password, recovery code, or decrypted manifest is committed to GitHub.
