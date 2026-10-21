import test from 'node:test';
import assert from 'node:assert/strict';
import { createDraft, diffBaseline, encodeDraft, decodeDraft } from '../src/inspection-outbox/core.js';
const ownerID='11111111-1111-4111-8111-111111111111',protocolID='22222222-2222-4222-8222-222222222222',id='33333333-3333-4333-8333-333333333333',at='2026-10-21T08:00:00.000Z';
const intrinsic=()=>({protocol:{id:protocolID,organization_id:null,created_by:ownerID,property_id:null,unit_id:null,protocol_type:'inspection',status:'draft',title:'Synthetic inspection',inspection_at:at,tenant_name:'Synthetic only',tenant_email:'fixture@example.invalid',general_notes:'Not customer data',completed_at:null,created_at:at,updated_at:at},rooms:[],findings:[]});
const joined=()=>{const value=intrinsic();value.protocol={...value.protocol,property_name:'Display name',property_street:'Display street',property_postal_code:'00000',property_city:'Display city',unit_label:'Display unit',unit_floor:'Display floor'};return value;};

test('actual joined GET display fields normalize to intrinsic transaction baseline',()=>{
 const source=joined(),before=JSON.stringify(source);const draft=createDraft({id,ownerID,organizationID:null,snapshot:source,at});assert.deepEqual(draft.baseline,intrinsic());assert.deepEqual(diffBaseline(source,intrinsic()),[]);assert.equal(JSON.stringify(source),before);const copy=decodeDraft(encodeDraft(draft),{ownerID,organizationID:null,protocolID});assert.deepEqual(copy.baseline,intrinsic());
});
test('normalization never removes intrinsic tenant notes, status or updated timestamps',()=>{
 const source=joined(),changed=intrinsic();changed.protocol.general_notes='Changed by team';assert.notDeepEqual(diffBaseline(source,changed),[]);changed.protocol.general_notes=source.protocol.general_notes;changed.protocol.updated_at='2026-10-21T09:00:00.000Z';assert.notDeepEqual(diffBaseline(source,changed),[]);
});
test('unexpected protocol or child fields fail closed instead of storing unrelated data',()=>{
 const source=joined();source.protocol.unexpected_auth_token='Never archive';assert.throws(()=>createDraft({id,ownerID,organizationID:null,snapshot:source,at}));
 const child=intrinsic();child.rooms=[{id:'44444444-4444-4444-8444-444444444444',name:'Kitchen',condition:'ok',notes:'',unexpected_secret:'Never archive'}];assert.throws(()=>createDraft({id,ownerID,organizationID:null,snapshot:child,at}));
});
