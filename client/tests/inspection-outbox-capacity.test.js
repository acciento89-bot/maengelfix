import test from 'node:test';
import assert from 'node:assert/strict';
import { createDraft, addFinding, sealBatch, validateDraft, canonicalJSON, encodeDraft, decodeDraft, rebaseDraft } from '../src/inspection-outbox/core.js';
import { OutboxTransport, sha256 } from '../src/inspection-outbox/transport.js';
const ceiling=1024*1024, at='2026-10-23T20:00:00.000Z';
const id=n=>`00000000-0000-4000-8000-${n.toString(16).padStart(12,'0')}`;
const ownerID=id(1),protocolID=id(2),operationID=id(3),scope={ownerID,organizationID:null,protocolID};
const wire=d=>canonicalJSON({version:1,operationID,protocolID,organizationID:null,baseline:d.baseline,rooms:d.rooms,findings:d.findings,photos:d.photos});
function boundary(extra=0) {
 const snapshot={protocol:{id:protocolID,organization_id:null,status:'draft',title:'Synthetic capacity',updated_at:at},rooms:[],findings:Array.from({length:300},(_,n)=>({id:id(100+n),room_id:null,title:'Existing',description:'x'.repeat(3000),category:'Other',severity:'normal',status:'open',attachment_count:0}))};
 let d=createDraft({id:id(4),ownerID,organizationID:null,snapshot,at});
 for(let n=0;n<50;n++)d=addFinding(d,{id:id(1000+n),roomID:null,title:'Local',description:'x',category:'Other',severity:'normal'});
 let remaining=ceiling+extra-Buffer.byteLength(wire(d),'utf8');assert.ok(remaining>0);
 for(const f of d.findings){const count=Math.min(2999,remaining);f.description+='x'.repeat(count);remaining-=count;}
 assert.equal(remaining,0);validateDraft(d);assert.equal(Buffer.byteLength(wire(d),'utf8'),ceiling+extra);return d;
}
function oldQueued(d){return {...structuredClone(d),revision:d.revision+1,state:'queued',operationID,batchPayload:wire(d)};}
test('complete publication accepts exact server byte ceiling but rejects one extra byte before sealing',()=>{
 const exact=boundary();assert.equal(Buffer.byteLength(sealBatch(exact,{operationID,at}).batchPayload,'utf8'),ceiling);
 const over=boundary(1),before=encodeDraft(over);assert.throws(()=>sealBatch(over,{operationID,at}),{code:'capacity'});assert.equal(encodeDraft(over),before);assert.equal(over.state,'draft');
 // Existing UI can shorten the preserved local finding and seal a new valid proposal.
 over.findings[0].description=over.findings[0].description.slice(1);assert.equal(sealBatch(over,{operationID,at}).state,'queued');
});
test('wire capacity counts UTF8 bytes rather than characters',()=>{
 const d=boundary(),ascii=wire(d);d.findings[0].description='€'+d.findings[0].description.slice(1);assert.equal(wire(d).length,ascii.length);assert.equal(Buffer.byteLength(wire(d),'utf8'),ceiling+2);assert.throws(()=>sealBatch(d,{operationID,at}),{code:'capacity'});
});
test('legacy oversized queued archive stays readable and requires explicit authoritative cancellation to edit',()=>{
 const old=oldQueued(boundary(1)),raw=encodeDraft(old);assert.deepEqual(decodeDraft(raw,scope),old);
 assert.throws(()=>rebaseDraft(old,old.baseline,{...scope,receiptAbsent:true,operationCancelled:false,confirmed:true}));
 const editable=rebaseDraft(old,old.baseline,{...scope,receiptAbsent:true,operationCancelled:true,confirmed:true});assert.equal(editable.state,'draft');assert.deepEqual(editable.findings,old.findings);assert.throws(()=>sealBatch(editable,{operationID,at}),{code:'capacity'});assert.equal(encodeDraft(old),raw);
});
test('legacy oversized publish performs no network write while hash-only receipt and cancel recovery remain available',async()=>{
 const old=oldQueued(boundary(1)),calls=[],payloadHash=await sha256(new Blob([old.batchPayload]));
 const transport=new OutboxTransport({isCurrentScope:()=>true,fetcher:async(url,options)=>{calls.push({url,options});const cancelled=url.endsWith('/cancel');return {ok:true,json:async()=>({exists:false,...scope,operationID,payloadHash,...(cancelled?{cancelled:true}:{})})};}});
 await assert.rejects(transport.publish(old,new Map()),{code:'capacity'});assert.equal(calls.length,0);
 assert.equal((await transport.receipt(old)).exists,false);assert.equal((await transport.cancel(old)).cancelled,true);assert.equal(calls.length,2);assert.ok(calls[0].url.includes(payloadHash));assert.deepEqual(JSON.parse(calls[1].options.body),{payloadHash});assert.ok(calls[1].options.body.length<100);
});
