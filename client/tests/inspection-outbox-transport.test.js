import test from 'node:test';
import assert from 'node:assert/strict';
import { createDraft, addRoom, sealBatch } from '../src/inspection-outbox/core.js';
import { OutboxTransport } from '../src/inspection-outbox/transport.js';
const ownerID='11111111-1111-4111-8111-111111111111',protocolID='22222222-2222-4222-8222-222222222222',id='33333333-3333-4333-8333-333333333333',roomID='44444444-4444-4444-8444-444444444444',operationID='55555555-5555-4555-8555-555555555555',at='2026-10-21T08:00:00.000Z';
const scope={ownerID,organizationID:null,protocolID};
const draft=()=>addRoom(createDraft({id,ownerID,organizationID:null,at,snapshot:{protocol:{id:protocolID,organization_id:null,status:'draft',title:'Synthetic',updated_at:at},rooms:[],findings:[]}}),{id:roomID,name:'Kitchen',condition:'ok',notes:''});
const queued=()=>sealBatch(draft(),{operationID,at});
const receipt=value=>({ownerID,protocolID,operationID,payload:value.batchPayload,result:{rooms:{[roomID]:'server-room'},findings:{},photos:{}}});
const response=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});

test('explicit queued publish sends immutable body through same-origin multipart and validates acknowledgement',async()=>{
 const value=queued(),calls=[];const transport=new OutboxTransport({isCurrentScope:()=>true,fetcher:async(url,options)=>{calls.push({url,options});return response({receipt:receipt(value)});}});assert.deepEqual(await transport.publish(value,new Map()),receipt(value));assert.equal(calls.length,1);assert.equal(calls[0].url,`/api/inspections/${protocolID}/offline-batches`);assert.equal(calls[0].options.credentials,'same-origin');assert.equal(calls[0].options.method,'POST');assert.equal(calls[0].options.body.get('payload'),value.batchPayload);assert.equal(calls[0].options.body.get('photoIDs'),'[]');assert.equal(value.state,'queued');
});
test('draft or foreign scope cannot trigger network and late account switch cannot accept receipt',async()=>{
 let calls=0;const blocked=new OutboxTransport({isCurrentScope:()=>false,fetcher:async()=>{calls++;}});await assert.rejects(blocked.publish(queued(),new Map()));await assert.rejects(blocked.publish(draft(),new Map()));assert.equal(calls,0);
 let current=true;const value=queued(),late=new OutboxTransport({isCurrentScope:()=>current,fetcher:async()=>{current=false;return response({receipt:receipt(value)});}});await assert.rejects(late.publish(value,new Map()));assert.equal(value.receipt,null);
});
test('network ambiguity remains queued and never invents success or automatically retries with a new key',async()=>{
 const value=queued();let calls=0;const transport=new OutboxTransport({isCurrentScope:()=>true,fetcher:async()=>{calls++;throw Error('Synthetic offline');}});await assert.rejects(transport.publish(value,new Map()),error=>error.code==='uncertain');assert.equal(calls,1);assert.equal(value.operationID,operationID);assert.equal(value.state,'queued');
});
test('malformed or mismatched success response cannot mark local data acknowledged',async()=>{
 const value=queued();for(const body of [{receipt:{...receipt(value),ownerID:roomID}},{receipt:{...receipt(value),payload:'changed'}},{}]){const transport=new OutboxTransport({isCurrentScope:()=>true,fetcher:async()=>response(body)});await assert.rejects(transport.publish(value,new Map()));assert.equal(value.receipt,null);}
});
test('authoritative absent receipt must match exact queued hash and scope before becoming rebase evidence',async()=>{
 const value=queued(),calls=[];const transport=new OutboxTransport({isCurrentScope:()=>true,fetcher:async(url)=>{calls.push(url);return response({exists:false,ownerID,protocolID,operationID,payloadHash:new URL(url,'https://fixture.invalid').searchParams.get('payloadHash')});}});const evidence=await transport.receipt(value);assert.equal(evidence.payload,value.batchPayload);assert.equal(evidence.exists,false);assert.equal(calls.length,1);assert.ok(calls[0].startsWith(`/api/inspections/${protocolID}/offline-batches/${operationID}?payloadHash=`));assert.equal(calls[0].includes('Kitchen'),false);
 const mismatched=new OutboxTransport({isCurrentScope:()=>true,fetcher:async()=>response({exists:false,ownerID,protocolID,operationID,payloadHash:'a'.repeat(64)})});await assert.rejects(mismatched.receipt(value));
});
test('entitlement expiry, access failure, conflict and unknown outcome remain distinct blocked results',async()=>{
 for(const [status,code]of [[401,'identity'],[403,'identity'],[402,'entitlement'],[409,'conflict'],[413,'capacity'],[503,'uncertain']]){const transport=new OutboxTransport({isCurrentScope:()=>true,fetcher:async()=>response({error:'Internal details ignored'},status)});await assert.rejects(transport.publish(queued(),new Map()),error=>error.code===code);}
});


test('only explicit server cancellation evidence can unlock an uncommitted operation',async()=>{
 const value=queued(),calls=[];const transport=new OutboxTransport({isCurrentScope:()=>true,fetcher:async(url,options)=>{calls.push({url,options});const body=JSON.parse(options.body);return response({exists:false,cancelled:true,ownerID,protocolID,operationID,payloadHash:body.payloadHash});}});
 const evidence=await transport.cancel(value);assert.equal(evidence.cancelled,true);assert.equal(evidence.payload,value.batchPayload);assert.equal(calls[0].url,`/api/inspections/${protocolID}/offline-batches/${operationID}/cancel`);assert.equal(calls[0].options.method,'POST');assert.equal(Object.keys(JSON.parse(calls[0].options.body)).join(','),'payloadHash');
 const falseEvidence=new OutboxTransport({isCurrentScope:()=>true,fetcher:async(_url,options)=>response({exists:false,cancelled:false,ownerID,protocolID,operationID,payloadHash:JSON.parse(options.body).payloadHash})});await assert.rejects(falseEvidence.cancel(value));
});
test('cancellation after commit accepts only the original real receipt',async()=>{
 const value=queued(),transport=new OutboxTransport({isCurrentScope:()=>true,fetcher:async()=>response({exists:true,receipt:receipt(value)})});assert.deepEqual(await transport.cancel(value),{exists:true,receipt:receipt(value)});assert.equal(value.state,'queued');
});
