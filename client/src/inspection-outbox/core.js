// Device-local additive inspection capture. This module performs no I/O.
const PHOTO_LIMIT = 3 * 1024 * 1024;
export const MAX_DRAFT_PHOTO_BYTES = 20 * 1024 * 1024;
export const MAX_DRAFT_METADATA_BYTES = 1024 * 1024;
export const MAX_BATCH_PAYLOAD_BYTES = 1024 * 1024;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export class OutboxError extends Error {
  constructor(code) { super(code); this.name = 'OutboxError'; this.code = code; }
}
function need(value, code = 'invalid') { if (!value) throw new OutboxError(code); }
function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value) && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null); }
function exact(value, fields) { need(object(value)); need(Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field))); }
function id(value) { need(typeof value === 'string' && uuid.test(value), 'identity'); return value.toLowerCase(); }
function text(value, limit, required = false) { need(typeof value === 'string' && [...value].length <= limit && (!required || value.trim().length > 0)); return value; }
function time(value) { need(typeof value === 'string' && Number.isFinite(Date.parse(value)) && new Date(value).toISOString() === value); return value; }
function count(value) { need(Number.isSafeInteger(value) && value >= 0); }
function bytes(value) { return new TextEncoder().encode(value).length; }
function clone(value) { return JSON.parse(JSON.stringify(value)); }
export function canonicalJSON(value) {
  if (Array.isArray(value)) return '[' + value.map(canonicalJSON).join(',') + ']';
  if (object(value)) return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonicalJSON(value[key])).join(',') + '}';
  need(value === null || ['string', 'boolean'].includes(typeof value) || typeof value === 'number' && Number.isFinite(value));
  return JSON.stringify(value);
}
function allowed(value, fields) { need(object(value) && Object.keys(value).every(key => fields.includes(key))); }
function baseline(value) {
  exact(value, ['protocol', 'rooms', 'findings']); need(object(value.protocol));
  const protocolFields = ['id', 'organization_id', 'property_id', 'unit_id', 'created_by', 'protocol_type', 'status', 'title', 'inspection_at', 'tenant_name', 'tenant_email', 'general_notes', 'completed_at', 'created_at', 'updated_at'];
  const displayFields = ['property_name', 'property_street', 'property_postal_code', 'property_city', 'unit_label', 'unit_floor'];
  allowed(value.protocol, [...protocolFields, ...displayFields]);
  id(value.protocol.id); need(value.protocol.organization_id === null || id(value.protocol.organization_id));
  text(value.protocol.title, 180, true); need(['draft', 'completed'].includes(value.protocol.status)); text(value.protocol.updated_at, 100, true);
  need(Array.isArray(value.rooms) && value.rooms.length <= 1000 && Array.isArray(value.findings) && value.findings.length <= 1000, 'capacity');
  const roomIDs = new Set();
  for (const room of value.rooms) {
    allowed(room, ['id', 'protocol_id', 'name', 'position', 'condition', 'notes', 'created_at']); const key = id(room.id); need(!roomIDs.has(key)); roomIDs.add(key);
    text(room.name, 120, true); need(['ok', 'notice', 'defect'].includes(room.condition)); need(room.notes === null || typeof room.notes === 'string'); if (room.notes !== null) text(room.notes, 1200);
    if (Object.hasOwn(room, 'protocol_id')) need(id(room.protocol_id) === id(value.protocol.id), 'identity');
  }
  const findingIDs = new Set();
  for (const finding of value.findings) {
    allowed(finding, ['id', 'protocol_id', 'room_id', 'created_by', 'title', 'description', 'category', 'severity', 'status', 'defect_case_id', 'created_at', 'updated_at', 'room_name', 'attachment_count']); const key = id(finding.id); need(!findingIDs.has(key)); findingIDs.add(key);
    need(finding.room_id === null || roomIDs.has(id(finding.room_id)), 'identity');
    text(finding.title, 180, true); text(finding.description, 3000, true); text(finding.category, 80, true);
    need(['minor', 'normal', 'urgent'].includes(finding.severity)); text(finding.status, 80, true); count(finding.attachment_count);
    if (Object.hasOwn(finding, 'protocol_id')) need(id(finding.protocol_id) === id(value.protocol.id), 'identity');
  }
  need(bytes(canonicalJSON(value)) <= MAX_DRAFT_METADATA_BYTES, 'capacity');
  const normalized = clone(value);
  for (const key of displayFields) delete normalized.protocol[key];
  for (const finding of normalized.findings) delete finding.room_name;
  return normalized;
}
function scopeMatches(draft, scope) {
  need(object(scope) && id(scope.ownerID) === draft.ownerID && id(scope.protocolID) === draft.protocolID && (scope.organizationID === null ? null : id(scope.organizationID)) === draft.organizationID, 'identity');
}
function validateRoom(value) {
  exact(value, ['id', 'name', 'condition', 'notes']); need(id(value.id) === value.id); text(value.name, 120, true); need(value.name === value.name.trim()); text(value.notes, 1200); need(['ok', 'notice', 'defect'].includes(value.condition));
}
function validateFinding(value, roomIDs) {
  exact(value, ['id', 'roomID', 'title', 'description', 'category', 'severity']); need(id(value.id) === value.id); need(value.roomID === null || roomIDs.has(id(value.roomID)), 'identity');
  text(value.title, 180, true); need(value.title === value.title.trim()); text(value.description, 3000, true); text(value.category, 80, true); need(['minor', 'normal', 'urgent'].includes(value.severity));
}
function validatePhoto(value, findingIDs) {
  exact(value, ['id', 'findingID', 'name', 'mime', 'size', 'sha256']); need(id(value.id) === value.id); need(findingIDs.has(id(value.findingID)), 'identity'); text(value.name, 250, true);
  need(['image/jpeg', 'image/png', 'image/webp'].includes(value.mime)); count(value.size); need(value.size > 0 && value.size <= PHOTO_LIMIT, 'capacity'); need(typeof value.sha256 === 'string' && /^[0-9a-f]{64}$/.test(value.sha256));
}
function payload(draft, operationID) {
  return canonicalJSON({ version: 1, operationID, protocolID: draft.protocolID, organizationID: draft.organizationID, baseline: draft.baseline, rooms: draft.rooms, findings: draft.findings, photos: draft.photos });
}
function validateReceipt(draft, receipt) {
  exact(receipt, ['operationID', 'protocolID', 'ownerID', 'payload', 'result']);
  need(receipt.operationID === draft.operationID && receipt.protocolID === draft.protocolID && receipt.ownerID === draft.ownerID && receipt.payload === draft.batchPayload, 'identity');
  exact(receipt.result, ['rooms', 'findings', 'photos']);
  for (const field of ['rooms', 'findings', 'photos']) {
    const mapping = receipt.result[field]; need(object(mapping));
    const expected = draft[field].map(item => item.id); need(Object.keys(mapping).length === expected.length && expected.every(key => Object.hasOwn(mapping, key)));
    Object.values(mapping).forEach(value => text(value, 120, true)); need(new Set(Object.values(mapping)).size === expected.length);
  }
}
const fields = ['schemaVersion', 'id', 'ownerID', 'organizationID', 'protocolID', 'revision', 'createdAt', 'updatedAt', 'baseline', 'rooms', 'findings', 'photos', 'state', 'operationID', 'batchPayload', 'receipt'];
export function validateDraft(value) {
  exact(value, fields); need(value.schemaVersion === 1, 'future'); need(id(value.id) === value.id && id(value.ownerID) === value.ownerID && id(value.protocolID) === value.protocolID, 'identity'); need(value.organizationID === null || id(value.organizationID) === value.organizationID, 'identity'); count(value.revision); time(value.createdAt); time(value.updatedAt); need(value.updatedAt >= value.createdAt);
  need(canonicalJSON(baseline(value.baseline)) === canonicalJSON(value.baseline)); need(id(value.baseline.protocol.id) === value.protocolID && (value.baseline.protocol.organization_id === null ? null : id(value.baseline.protocol.organization_id)) === value.organizationID, 'identity');
  need(Array.isArray(value.rooms) && value.rooms.length <= 20 && Array.isArray(value.findings) && value.findings.length <= 50 && Array.isArray(value.photos) && value.photos.length <= 250, 'capacity');
  const roomIDs = new Set(value.baseline.rooms.map(room => id(room.id))), allIDs = new Set([value.id]);
  for (const room of value.rooms) { validateRoom(room); need(!roomIDs.has(room.id) && !allIDs.has(room.id)); roomIDs.add(room.id); allIDs.add(room.id); }
  const findingIDs = new Set();
  for (const finding of value.findings) { validateFinding(finding, roomIDs); need(!allIDs.has(finding.id) && !value.baseline.findings.some(item => id(item.id) === finding.id)); allIDs.add(finding.id); findingIDs.add(finding.id); }
  let photoBytes = 0;
  for (const photo of value.photos) { validatePhoto(photo, findingIDs); need(!allIDs.has(photo.id)); allIDs.add(photo.id); photoBytes += photo.size; }
  need(photoBytes <= MAX_DRAFT_PHOTO_BYTES && value.findings.every(finding => value.photos.filter(photo => photo.findingID === finding.id).length <= 5), 'capacity');
  need(['draft', 'queued', 'acknowledged'].includes(value.state));
  if (value.state === 'draft') need(value.operationID === null && value.batchPayload === null && value.receipt === null);
  else { need(id(value.operationID) === value.operationID && value.batchPayload === payload(value, value.operationID)); need(value.rooms.length > 0 || value.findings.length > 0); if (value.state === 'queued') need(value.receipt === null); else validateReceipt(value, value.receipt); }
  need(bytes(canonicalJSON(value)) <= 3 * MAX_DRAFT_METADATA_BYTES, 'capacity');
  return value;
}
export function createDraft({ id: draftID, ownerID, organizationID, snapshot, at }) {
  const source = baseline(snapshot); need(source.protocol.status === 'draft', 'conflict');
  return validateDraft({ schemaVersion: 1, id: id(draftID), ownerID: id(ownerID), organizationID: organizationID === null ? null : id(organizationID), protocolID: id(source.protocol.id), revision: 0, createdAt: time(at), updatedAt: at, baseline: source, rooms: [], findings: [], photos: [], state: 'draft', operationID: null, batchPayload: null, receipt: null });
}
function change(draft, field, value) { validateDraft(draft); need(draft.state === 'draft', 'conflict'); return validateDraft({ ...clone(draft), [field]: [...clone(draft[field]), clone(value)], revision: draft.revision + 1 }); }
export function addRoom(draft, room) { return change(draft, 'rooms', { ...room, id: id(room.id), name: text(room.name, 120, true).trim() }); }
export function addFinding(draft, finding) { return change(draft, 'findings', { ...finding, id: id(finding.id), roomID: finding.roomID === null ? null : id(finding.roomID), title: text(finding.title, 180, true).trim() }); }
export function addPhoto(draft, photo) { return change(draft, 'photos', { ...photo, id: id(photo.id), findingID: id(photo.findingID) }); }
export function sealBatch(draft, { operationID, at }) {
  validateDraft(draft); need(draft.state === 'draft' && draft.baseline.protocol.status === 'draft', 'conflict'); time(at); need(at >= draft.updatedAt); const operation = id(operationID);
  // Keep older queued archives readable for their existing hash-only receipt/cancel recovery.
  // Apply the server wire ceiling before publishing a NEW immutable operation instead.
  const batchPayload = payload(draft, operation); need(bytes(batchPayload) <= MAX_BATCH_PAYLOAD_BYTES, 'capacity');
  return validateDraft({ ...clone(draft), revision: draft.revision + 1, updatedAt: at, state: 'queued', operationID: operation, batchPayload });
}
export function acknowledgeBatch(draft, receipt, scope) {
  validateDraft(draft); scopeMatches(draft, scope); need(draft.state !== 'draft', 'conflict'); validateReceipt(draft, receipt);
  if (draft.state === 'acknowledged') { need(canonicalJSON(draft.receipt) === canonicalJSON(receipt), 'conflict'); return clone(draft); }
  return validateDraft({ ...clone(draft), state: 'acknowledged', receipt: clone(receipt), revision: draft.revision + 1 });
}
export function rebaseDraft(draft, snapshot, options) {
  validateDraft(draft); scopeMatches(draft, options); need(draft.state === 'queued' && options.receiptAbsent === true && options.operationCancelled === true && options.confirmed === true, 'conflict');
  const source = baseline(snapshot); need(source.protocol.status === 'draft' && id(source.protocol.id) === draft.protocolID && (source.protocol.organization_id === null ? null : id(source.protocol.organization_id)) === draft.organizationID, 'identity');
  return validateDraft({ ...clone(draft), baseline: source, state: 'draft', operationID: null, batchPayload: null, receipt: null, revision: draft.revision + 1 });
}
export function diffBaseline(before, after) {
  before = baseline(before); after = baseline(after); const differences = [];
  function compare(left, right, path) {
    if (canonicalJSON(left) === canonicalJSON(right)) return;
    if (object(left) && object(right)) {
      for (const key of new Set([...Object.keys(left), ...Object.keys(right)])) {
        if (!Object.hasOwn(left, key) || !Object.hasOwn(right, key)) differences.push({ path: path + '.' + key, before: left[key] ?? null, after: right[key] ?? null });
        else compare(left[key], right[key], path + '.' + key);
      }
    } else differences.push({ path, before: clone(left), after: clone(right) });
  }
  const normalize = input => ({ ...input, rooms: [...input.rooms].sort((a,b) => a.id.localeCompare(b.id)), findings: [...input.findings].sort((a,b) => a.id.localeCompare(b.id)) });
  compare(normalize(before), normalize(after), 'inspection'); return differences;
}
export function encodeDraft(draft) { validateDraft(draft); return canonicalJSON(draft); }
export function decodeDraft(raw, scope) { need(typeof raw === 'string' && bytes(raw) <= 3 * MAX_DRAFT_METADATA_BYTES, 'capacity'); const draft = validateDraft(JSON.parse(raw)); scopeMatches(draft, scope); return draft; }
