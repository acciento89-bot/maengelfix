# Offline Inspection Outbox Implementation Plan

> For agentic workers: use superpowers:executing-plans inline, no child agents. Coordinator exclusively executes tests/builds/native operations. Spec: ../specs/2026-10-21-offline-inspection-design.md.

- [x] Audit exact fresh canonical source, existing features, authorization, retries and native host.
- [x] Set conservative additive design; no cold airplane launch or case-conversion claim.
- [x] Write client/tests/inspection-outbox.test.js importing missing client/src/inspection-outbox/core.js, plus repository test adapter and server batch tests before corresponding production. Ask root exact Node RED; inspect actual missing symbols/assertions.
- [x] After actual RED implement pure createDraft/addRoom/addFinding/addPhoto/sealBatch/reconcileReceipt/diffBaseline transitions. Strict identity/bounds/immutable queued payload. Request root core GREEN.
- [x] Write repository fault/conflict RED, then IndexedDB atomic archive+Blob transaction and injectable adapter. Request root GREEN; no native execution by worker.
- [x] Write transactional receipt/conflict/file cleanup RED. Implement server/inspection-outbox.js injected coordinator + narrow route and receipt table, leaving auth/privateProFeature/inspectionAccess/quotas/billing unchanged. Root actual isolated PostgreSQL17 suite and old billing regressions GREEN. No migration applied by worker.
- [x] Integrate separate InspectionOutbox.jsx and scoped inspection entry, explicit upload/conflict/local deletion, owner lifecycle and late-callback guards. Preserve existing room/finding/PDF/conversion routes. Responsive DE/EN controls and safe-area style.
- [x] Root client build/existing server tests, independent web/backend review and actual browser dirty-guard regressions.
- [ ] Root Android wrapper/native UI/Duo acceptance; separate canonical iOS native port build/acceptance (ongoing isolated ios-app checkout).
- [ ] Record exact commit/files/evidence/limitations, metadata proposal and actual native QA checklist. Commit only verified scoped code, no push/version/deployment/store actions.

Each behavior begins with observed failing root test and ends with actual root GREEN. Do not claim native acceptance from source/build/pure tests. Root owns all server/customer actions and deployment decisions.

Final web verification:32 client PASS,21 server PASS+1SKIP, Vite PASS; prior isolated realPG11PASS. Root actual synthetic browser Cancel/Confirm/select-only checks PASS. Detailed delivery distinctions in ../offline-inspection-handoff.md.

## 2026-10-23 canonical publication capacity correction

Independent read-only review located a valid sub-1MiB baseline plus permitted additions whose complete canonical publication exceeds the server multipart-field/decoder1MiB ceiling. Preserve the3MiB local draft/archive budget and old queued-record decoding: tightening the shared payload serializer would otherwise make legacy oversized queues unreadable and prevent their existing hash-only receipt/cancel/rebase recovery.

- [x] Observe RED for valid oversized draft sealing; exact1MiB/one-byte-over and multibyte UTF8 boundaries.
- [x] Add complete-wire limit immediately before sealing and before actual publish network activity. Keep receipt/cancel/read/rebase paths compatible with old queued records.
- [x] Observe GREEN including legacy hash-only recovery and unchanged/editable draft after rejection; run client/server regression suites and production client build.
- [ ] Independent follow-up source review, normal integration and scoped web deployment with exact live source evidence. No customer data, fixture entitlement, purchase, credentials or Android binary changes.

Real multipart regression additionally observed exact1MiB rejected by Busboy at equality. Scoped outbox parser allows one sentinel byte, while canonical decoder/client retain inclusive1MiB. Exact/+1/multibyte real HTTP checks, all44 client/route/multipart tests,11 isolated PostgreSQL transaction checks plus7 routes, and Vite build pass. Independent final source review reports no P1/P2. No live database or reviewer entitlement changed. Integration and live deployment still pending.
