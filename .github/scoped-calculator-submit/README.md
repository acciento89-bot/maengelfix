# Nine existing calculators: manual Google update

The workflow is installed in the own repository. The owner completed the bounded inspection described below; no production submission has been dispatched through this workflow. Local tests use synthetic fixtures and fake transports. They do not prove real signed artifacts, native QA or provider acceptance.

## Completed inspection and pinned existing locales

The owner dispatched `operation=inspect`, `package=all-nine` on main in [run 40886103485](https://github.com/acciento89-bot/maengelfix/actions/runs/40886103485), source commit `b09730d9cf897e0283f678ab2aaa981b2d915bee`. Its original artifact ID is `12901384975`. The retained full original `locale-inventory.json` has SHA256 `35b9bd17b4106820a156e8ca192ba3e66cf9cda0f2e3952b7ed1fb509aee57aa`; every exact catalog package returned existing `de-DE` and `en-US`, with all nine owned edit deletions confirmed HTTP 204. These actual 18 locale IDs and the immutable original receipt SHA are now pinned in every app catalog entry; the existing DE/EN release-note keys already match. Preserve `.github/navoops-preflight/**` and `navoops-google-track-audit.yml` unchanged. No schedule, branch event, rerun or other package is supported.

The inspect job uses the existing WIF route. For each exact catalog package it creates one owned temporary edit, GETs listings, retains only sorted existing language IDs and confirms DELETE before continuing. It never reads candidate assets or mutates uploads, images, tracks or review state. Unknown creation or deletion stops the batch as reconciliation required. Do not run other edits/Console mutations for these apps concurrently. Do not repeat a failed operation blindly; review its owned edit identity and outcome first.

Every candidate must include the exact unmodified original inspection receipt at `qa/locale-inventory.json`; its raw SHA must equal the frozen catalog snapshot SHA. The verifier still rejects missing/null locale pins, a different snapshot, an absent selected existing locale or unconfirmed cleanup. Do not fabricate or rewrite an inspection receipt. The inventory's earlier catalog hash records its pre-freeze input; it is not rewritten to manufacture a circular new hash. Any future inventory/pin change requires separate review, not an automatic loop.

## Prepare genuine candidate evidence

Use the original successful selected main source/sign runs at the catalog's exact reviewed source commit. Retain the ORIGINAL GitHub signed-artifact ZIP, its official archive digest/artifact ID, and the exact AAB it contains. No reconstructed ZIP, debug build, version override, unrelated green run or re-signed local AAB qualifies. The candidate verifier checks jarsigner, the pinned central certificate fingerprints, pinned official bundletool package/version, every raw font/OFL/notice byte and official source/sign run/artifact metadata.

From this exact signed AAB derive and install the normal Android app for genuine launch/main/navigation/font/asset QA. Preserve the derived/installed APK SHA and the original command/output proof binding it to the AAB. Do not perform purchases, restores, redemptions or ad impressions. The owner reviews the evidence; JSON claims and hashes cannot independently establish that the claimed human QA happened.

Capture four distinct real phone frames per selected existing locale (validator accepts4–8). The owner plans1080×1920. Retain every original opaque native RGBA/RGB PNG. Encode lossless RGB24 PNG without alpha or resizing; decoded RGB pixels and dimensions must equal the raw capture. Record raw SHA, upload SHA and SHA256 of row-major decoded RGB bytes (no header/filter/alpha bytes). The validator checks full PNG CRC/decompression, all five row filters, opacity,320–3840px sides and maximum2:1 ratio. Current720×1600 QA-only frames fail and must never be candidates. No fabricated/localized overlay or editor/demo screenshot is allowed. Different actual locales have separate bound files. Optional icon is only the exact catalog-pinned original512PNG.

The JSON templates intentionally contain invalid placeholders and `PENDING`, never fake passing evidence. Fill them from actual receipts and exact files. Candidate ZIP layout:

```
manifest.json
bundle/app.aab
provenance/signed-ci-artifact.zip
qa/locale-inventory.json
qa/native-qa.json
qa/derived-apk-proof.json
qa/<actual hash-listed proof files>
raw/<existing-locale>/01.png ... 04.png
screens/<existing-locale>/01.png ... 04.png
```

Only explicitly hash-listed files are allowed. No traversal, aliases, duplicate ZIP/JSON identities, symlinks or extra files. The candidate ZIP is uploaded by the owner as a NEW asset of a private draft release in the same maengelfix repository. Its required name is `calculator-candidate-{package}-1.2.0-{catalog-code}.zip`. Retain its immutable asset ID and raw archive SHA256. Do not replace an existing frozen release asset.

## Explicit single-package submission

Only after genuine native/rights/release review, dispatch once on main with `operation=submit`, ONE allowed package, the own draft asset ID and reviewed raw archive SHA. `all-nine` is rejected in this mode. No free URL, version, track, review-behavior or locale input exists.

Prepare has no Google identity. It verifies the draft, exact original signed artifact/provenance, candidate and official source/sign runs, then transfers exactly candidate.zip and a hash-bound attestation by immutable Actions artifact ID. Submit re-verifies the same candidate/run/catalog bytes before existing WIF authentication, then again before its single owned edit.

Fresh production must be one completed release at the catalog previous code; fresh global max across APKs/bundles/tracks must equal previousMax, and new=max+1. Only raw AAB upload, selected existing phone screenshots/optional original icon and exact production version/notes are written. Existing listing text/details/countries/nonproduction tracks are compared unchanged. Production targeting/priority fields are retained. Validate precedes one commit with `changesInReviewBehavior=ERROR_IF_IN_REVIEW`; there is no omitted/default/CANCEL path or retry.

Known precommit errors delete only owned uncommitted edits and confirm absence. A commit timeout, throttling,5xx or malformed success is `reconciliation_required`: no retry and no deletion of a possibly committing edit. A known in-review rejection stops without cancelling review. Acknowledged commit gets a NEW owned readback edit, checks exact bytes/track/images and preserved unrelated data, then confirms its deletion. An exact already-present candidate is a read-only no-op. Conflicting/partially uploaded new codes stop for reconciliation. Workflow reruns are blocked. A successful receipt means submitted for review; it does not confirm public release.

## Safe local checks

From the repository root, with no credentials or network:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .github/scoped-calculator-submit/tests -v
```

Official reference: [listing inventory](https://developers.google.com/android-publisher/api-ref/rest/v3/edits.listings/list), [edit deletion](https://developers.google.com/android-publisher/api-ref/rest/v3/edits/delete), [commit review behavior](https://developers.google.com/android-publisher/api-ref/rest/v3/edits/commit), [Google screenshot requirements](https://support.google.com/googleplay/android-developer/answer/9866151).
