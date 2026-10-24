# Native Inspection Outbox Implementation Plan

> For agentic workers: execute inline using superpowers:executing-plans; no children. Root owns all runtimes. Spec ../specs/2026-10-21-native-inspection-outbox-design.md.

- [x] Fresh ios-app source audit/isolation and native-vs-web provenance recorded.
- [x] Author ios/Tests/InspectionOutboxTests.swift; request exact root swiftc RED with missing Core/InspectionOutbox.swift + Core/InspectionArchive.swift. No model production before observedRED.
- [x] Implement strict canonical JSON/wire/core transitions and atomic account archive with deleted-owner barrier/batch photos; request root GREEN plus actual JS/native Unicode wire parity fixture.
- [x] Add only new API methods reusing original private rawData/makeRequest/session/validate; preserve all old API behavior byte-for-byte and source StoreKit/AppSession/case functions.
- [x] Add native list/detail/online protocol create and native local outbox sheets/photo/camera/receipt/cancel/conflict UI, new tab only. Fresh signed-in actor/scope access guards and semantic dirty prompts.
- [x] Root pure35/API15/wire interoperability, generic iOS build5, independent wholefeature review; one payload-capacity P2 found and corrected before delivery.
- [ ] Root actual synthetic native UI/Photos/cold resume/account transition/narrow-wide-Duo acceptance. External fixture prepared separately; no claim from source/build.
- [ ] Verify protected hashes, docs/nativeQA/metadata, local scoped native commit. No version/push/release/sign/store actions. Root integrates separate web/backend/native branches safely.

Final source evidence: all11 independent-reviewed inputs exact; all8 original protected hashes unchanged; verified tracked pbxproj adds16 registration lines only, no settings changes. NativeSources remain identical to root build5. Full handoff: ../native-inspection-handoff.md.


23 October review correction: backend `decodePayload` caps the entire canonical UTF-8 payload at 1 MiB. Native `payload` now enforces the same inclusive boundary before a draft can be sealed or an existing queued record validated. Actual regression first failed because 1 MiB + 1 byte was accepted; now all 38 core checks pass, including exact 1 MiB acceptance, UTF-8 counting and unchanged editable draft after capacity failure. Source-only evidence; native runtime/archive refresh still required before upload.


## Native Duo acceptance — 24 October 2026

The actual native app saved one neutral room and finding in the owner's isolated review fixture. No customer records were used. The first photo-import acceptance check failed with zero photos: presenting PhotosPicker from a recycled Form row repeatedly entered native presentation/layout work. A full-screen-cover-only hypothesis failed and was reverted. A diagnostic lifecycle trace ruled out the proposed premature account/lifetime invalidation; the temporary instrumentation was removed.

The system picker now belongs to a stable root presenter, with the selected finding and draft captured and the existing owner/lifetime checks retained. Real system-picker input selected the app's own neutral icon. The persisted JPEG, size, hash, finding link and visible thumbnail passed; a complete app restart restored the same thumbnail and one room, finding and photo.

Actual future-format injection blocked writes and preserved the injected file; the acknowledged original was restored byte for byte. An actual directory-permission write failure displayed an error, retained the unsaved input and left the original archive unchanged. Permissions were restored and the normal discard guard preserved saved records. Successful Reload now clears an obsolete error before loading the gallery, while gallery failures still retain their own error/block. This recovery correction passed a separate native failure/recovery check in the final Debug build.

The real explicit seal/publish flow produced an immutable operation and matching durable server receipt. Independent authenticated readback confirmed exactly one room, finding and attachment, with the protocol still a draft and no converted case. The server PDF returned successfully; the native share sheet opened and was dismissed without sending. No purchases, restores, redemption, messages or customer-account writes occurred.

Current source compilation and tests: 38 outbox/archive checks and 15 API checks passed. The existing unnecessary `try` warning in InspectionOutboxTests.swift:20 remains. Independent read-only review found no P1/P2 in the picker/recovery changes. Three genuine unframed Duo camera captures (one Closed and two Open) and original hashes are retained with the release evidence; JPEG encoding is the only upload transformation. This is not a claim of maximum Dynamic Type acceptance.

Shipping gates: refresh and verify the Release archive/local signature, confirm all three Duo images COMPLETE in the editable Apple version, then upload/select the exact build and submit once. No release or submission is implied by this native acceptance record.
