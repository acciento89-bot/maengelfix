import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import * as implementation from '../src/inspection-outbox/repository.js';
import { createDraft,addRoom,addFinding,addPhoto } from '../src/inspection-outbox/core.js';
const ownerID='11111111-1111-4111-8111-111111111111',protocolID='22222222-2222-4222-8222-222222222222',draftID='33333333-3333-4333-8333-333333333333',roomID='44444444-4444-4444-8444-444444444444',findingID='55555555-5555-4555-8555-555555555555',photoID='66666666-6666-4666-8666-666666666666',foreignID='99999999-9999-4999-8999-999999999999',at='2026-10-21T08:00:00.000Z';
const scope={ownerID,organizationID:null,protocolID},key=(scope,id)=>JSON.stringify([scope.ownerID,scope.organizationID,scope.protocolID,id]);
const deferred=()=>{let resolve;const promise=new Promise(value=>{resolve=value;});return{promise,resolve};};
class AtomicStore {
 records=new Map();blobs=new Map();deleted=new Set();tail=Promise.resolve();calls=0;pauseCall=0;paused=deferred();resume=deferred();
 async transaction(owner,action){
  const call=++this.calls;if(call===this.pauseCall){this.paused.resolve();await this.resume.promise;}
  const job=this.tail.catch(()=>{}).then(async()=>{
   const records=new Map(this.records),blobs=new Map(this.blobs),deleted=new Set(this.deleted);
   const tx={isOwnerDeleted:async()=>deleted.has(owner),markOwnerDeleted:async()=>deleted.add(owner),deleteOwnerData:async()=>{for(const[k,row]of records)if(row.scope.ownerID===owner)records.delete(k);for(const k of blobs.keys())if(JSON.parse(k)[0]===owner)blobs.delete(k);},listOwner:async()=>[...records.values()].filter(row=>row.scope.ownerID===owner),getDraft:async(scope,id)=>records.get(key(scope,id))?.bytes??null,putDraft:async(scope,id,bytes)=>records.set(key(scope,id),{scope:{...scope},id,bytes}),deleteDraft:async(scope,id)=>records.delete(key(scope,id)),getBlob:async(scope,id)=>blobs.get(key(scope,id))??null,putBlob:async(scope,id,blob)=>blobs.set(key(scope,id),blob),deleteBlob:async(scope,id)=>blobs.delete(key(scope,id))};
   const value=await action(tx);this.records=records;this.blobs=blobs;this.deleted=deleted;return value;
  });this.tail=job;return job;
 }
 async fixtureDeleteOwner(owner){await this.transaction(owner,async tx=>{await tx.markOwnerDeleted();await tx.deleteOwnerData();});}
}
function value(id=draftID,photo=photoID){
 const bytes=new Uint8Array([137,80,78,71]),blob=new Blob([bytes],{type:'image/png'});let draft=createDraft({id,ownerID,organizationID:null,at,snapshot:{protocol:{id:protocolID,organization_id:null,status:'draft',title:'Synthetic only',updated_at:at},rooms:[],findings:[]}});
 draft=addRoom(draft,{id:roomID,name:'Kitchen',condition:'ok',notes:''});draft=addFinding(draft,{id:findingID,roomID,title:'Window',description:'Synthetic only',category:'Other',severity:'normal'});draft=addPhoto(draft,{id:photo,findingID,name:'synthetic.png',mime:'image/png',size:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')});return{draft,photos:new Map([[photo,blob]])};
}
test('save paused before its write transaction cannot resurrect owner data after atomic deletion',{timeout:5000},async()=>{
 const store=new AtomicStore(),repo=new implementation.OutboxRepository(store,scope),{draft,photos}=value();store.pauseCall=2;
 const saving=repo.save(draft,photos,null);await store.paused.promise;
 await store.fixtureDeleteOwner(ownerID);store.resume.resolve();await assert.rejects(saving);assert.equal(store.records.size,0);assert.equal(store.blobs.size,0);assert.equal(store.deleted.has(ownerID),true);
});
test('account purge marks deletion and clears malformed archive plus orphan photos without parsing them',async()=>{
 const store=new AtomicStore(),otherScope={...scope,ownerID:foreignID};store.records.set(key(scope,draftID),{scope,id:draftID,bytes:'corrupt protected original'});store.records.set(key(otherScope,draftID),{scope:otherScope,id:draftID,bytes:'foreign archive unchanged'});store.blobs.set(key(scope,photoID),new Blob(['private orphan']));store.blobs.set(key(otherScope,photoID),new Blob(['foreign untouched']));
 assert.equal(typeof implementation.purgeOutboxOwner,'function');await implementation.purgeOutboxOwner(store,ownerID);assert.equal(store.records.has(key(scope,draftID)),false);assert.equal(store.blobs.has(key(scope,photoID)),false);assert.equal(store.deleted.has(ownerID),true);assert.equal(store.records.get(key(otherScope,draftID)).bytes,'foreign archive unchanged');assert.equal(await store.blobs.get(key(otherScope,photoID)).text(),'foreign untouched');
 const repo=new implementation.OutboxRepository(store,scope),{draft,photos}=value();await assert.rejects(repo.save(draft,photos,null));
});
test('gallery or publish gets selected draft photo map with one owner integrity snapshot',async()=>{
 const store=new AtomicStore(),repo=new implementation.OutboxRepository(store,scope),{draft,photos}=value();await repo.save(draft,photos,null);let reads=0;const original=repo.ownerSnapshot.bind(repo);repo.ownerSnapshot=async()=>{reads++;return original();};
 const map=await repo.photos(draft.id);assert.equal(reads,1);assert.equal(map.size,1);assert.equal(map.get(photoID).size,4);assert.equal((await map.get(photoID).arrayBuffer()).byteLength,4);
});
test('batch photo read still rejects corrupt other-draft photos belonging to same owner',async()=>{
 const store=new AtomicStore(),repo=new implementation.OutboxRepository(store,scope),first=value(),second=value('77777777-7777-4777-8777-777777777777','88888888-8888-4888-8888-888888888888');await repo.save(first.draft,first.photos,null);await repo.save(second.draft,second.photos,null);store.blobs.set(key(scope,'88888888-8888-4888-8888-888888888888'),new Blob([new Uint8Array([1,2,3,4])],{type:'image/png'}));await assert.rejects(repo.photos(first.draft.id));assert.equal(store.records.size,2);assert.equal(store.blobs.size,2);
});
