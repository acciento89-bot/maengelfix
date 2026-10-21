import test from 'node:test';
import assert from 'node:assert/strict';
import { createDraft, addRoom, addFinding, addPhoto, sealBatch, acknowledgeBatch, rebaseDraft, diffBaseline, encodeDraft, decodeDraft } from '../src/inspection-outbox/core.js';
const ownerID='11111111-1111-4111-8111-111111111111', protocolID='22222222-2222-4222-8222-222222222222';
const draftID='33333333-3333-4333-8333-333333333333',roomID='44444444-4444-4444-8444-444444444444',findingID='55555555-5555-4555-8555-555555555555',photoID='66666666-6666-4666-8666-666666666666',operationID='77777777-7777-4777-8777-777777777777';
const at='2026-10-21T08:00:00.000Z';
const snapshot=()=>({protocol:{id:protocolID,organization_id:null,status:'draft',title:'Synthetic inspection',updated_at:at},rooms:[],findings:[]});
const empty=()=>createDraft({id:draftID,ownerID,organizationID:null,snapshot:snapshot(),at});
const room=()=>addRoom(empty(),{id:roomID,name:'Kitchen',condition:'notice',notes:'Synthetic source'});
const finding=()=>addFinding(room(),{id:findingID,roomID,title:'Window',description:'Synthetic draft only',category:'Fenster',severity:'normal'});
const scope={ownerID,organizationID:null,protocolID};

test('local room/finding capture is isolated and leaves authorized baseline unchanged',()=>{
 const original=empty(),saved=finding();assert.equal(original.rooms.length,0);assert.equal(saved.rooms.length,1);assert.equal(saved.findings[0].roomID,roomID);assert.deepEqual(saved.baseline,snapshot());assert.equal(saved.state,'draft');assert.equal(saved.receipt,null);
 assert.throws(()=>addFinding(room(),{id:findingID,roomID:'88888888-8888-4888-8888-888888888888',title:'X',description:'Y',category:'Other',severity:'normal'}));
});
test('visible invalid/duplicate or over-limit values cannot be captured',()=>{
 assert.throws(()=>addRoom(empty(),{id:roomID,name:'   ',condition:'ok',notes:''}));
 assert.throws(()=>addRoom(room(),{id:roomID,name:'Duplicate',condition:'ok',notes:''}));
 assert.throws(()=>addFinding(room(),{id:findingID,roomID,title:'X',description:'',category:'Other',severity:'normal'}));
 assert.throws(()=>addFinding(room(),{id:findingID,roomID,title:'X'.repeat(181),description:'Y',category:'Other',severity:'normal'}));
 assert.throws(()=>createDraft({id:draftID,ownerID,organizationID:null,snapshot:{...snapshot(),protocol:{...snapshot().protocol,status:'completed'}},at}));
});
test('photo metadata is bounded, attached only to a new finding, and remains local',()=>{
 const input=finding(),photo={id:photoID,findingID,name:'synthetic.png',mime:'image/png',size:8,sha256:'a'.repeat(64)};
 const saved=addPhoto(input,photo);assert.equal(input.photos.length,0);assert.deepEqual(saved.photos,[photo]);
 assert.throws(()=>addPhoto(input,{...photo,mime:'application/pdf'}));assert.throws(()=>addPhoto(input,{...photo,size:3*1024*1024+1}));assert.throws(()=>addPhoto(input,{...photo,sha256:'invalid'}));assert.throws(()=>addPhoto(input,{...photo,findingID:photoID}));
});
test('queued operation is stable immutable and never reports sent before matching receipt',()=>{
 const queued=sealBatch(finding(),{operationID,at});assert.equal(queued.state,'queued');assert.equal(queued.operationID,operationID);assert.equal(queued.receipt,null);
 assert.throws(()=>addRoom(queued,{id:photoID,name:'Late',condition:'ok',notes:''}));assert.throws(()=>sealBatch(queued,{operationID:photoID,at}));
 const receipt={operationID,protocolID,ownerID,payload:queued.batchPayload,result:{rooms:{[roomID]:'server-room'},findings:{[findingID]:'server-finding'},photos:{}}};
 const ack=acknowledgeBatch(queued,receipt,scope);assert.equal(ack.state,'acknowledged');assert.deepEqual(ack.receipt,receipt);assert.deepEqual(acknowledgeBatch(ack,receipt,scope),ack);
 assert.throws(()=>acknowledgeBatch(queued,{...receipt,ownerID:photoID},scope));assert.throws(()=>acknowledgeBatch(queued,{...receipt,payload:'altered'},scope));
});
test('same-account and scope boundaries reject cold foreign archive or late acknowledgements',()=>{
 const saved=finding(),bytes=encodeDraft(saved);assert.deepEqual(decodeDraft(bytes,scope),saved);assert.throws(()=>decodeDraft(bytes,{...scope,ownerID:photoID}));assert.throws(()=>decodeDraft(bytes,{...scope,organizationID:photoID}));assert.throws(()=>decodeDraft(bytes,{...scope,protocolID:photoID}));
});
test('corrupt future trailing and foreign references cannot replace a valid saved draft',()=>{
 const bytes=encodeDraft(finding());assert.throws(()=>decodeDraft(bytes+'trailing',scope));assert.throws(()=>decodeDraft(JSON.stringify({...finding(),schemaVersion:99}),scope));assert.throws(()=>decodeDraft(JSON.stringify({...finding(),findings:[{...finding().findings[0],roomID:photoID}]}),scope));assert.equal(decodeDraft(bytes,scope).findings.length,1);
});
test('conflicts detect actual child changes even when protocol updated_at is unchanged',()=>{
 const baseline=snapshot(),current=snapshot();current.rooms=[{id:roomID,name:'Server room',condition:'ok',notes:''}];assert.notDeepEqual(diffBaseline(baseline,current),[]);assert.deepEqual(diffBaseline(baseline,JSON.parse(JSON.stringify(baseline))),[]);
 const photoChange=snapshot();photoChange.findings=[{id:findingID,room_id:null,title:'Server finding',description:'Existing',category:'Other',severity:'normal',status:'open',attachment_count:1}];const newer=structuredClone(photoChange);newer.findings[0].attachment_count=2;assert.notDeepEqual(diffBaseline(photoChange,newer),[]);
});
test('queued rebase requires authoritative absent receipt and explicit review confirmation',()=>{
 const queued=sealBatch(finding(),{operationID,at}),fresh=snapshot();fresh.protocol.title='Changed by team';
 assert.throws(()=>rebaseDraft(queued,fresh,{...scope,receiptAbsent:false,confirmed:true}));assert.throws(()=>rebaseDraft(queued,fresh,{...scope,receiptAbsent:true,confirmed:false}));
 assert.throws(()=>rebaseDraft(queued,fresh,{...scope,receiptAbsent:true,operationCancelled:false,confirmed:true}));const next=rebaseDraft(queued,fresh,{...scope,receiptAbsent:true,operationCancelled:true,confirmed:true});assert.equal(next.state,'draft');assert.equal(next.operationID,null);assert.equal(next.baseline.protocol.title,'Changed by team');assert.deepEqual(next.findings,queued.findings);
});
