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
