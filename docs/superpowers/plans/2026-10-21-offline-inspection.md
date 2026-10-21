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
