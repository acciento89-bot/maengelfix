import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createDraft, addRoom, addFinding, addPhoto, sealBatch, decodeDraft } from '../src/inspection-outbox/core.js';
import { OutboxRepository } from '../src/inspection-outbox/repository.js';
const ownerID='11111111-1111-4111-8111-111111111111', protocolID='22222222-2222-4222-8222-222222222222',id='33333333-3333-4333-8333-333333333333',roomID='44444444-4444-4444-8444-444444444444',findingID='55555555-5555-4555-8555-555555555555',photoID='66666666-6666-4666-8666-666666666666';
const scope={ownerID,organizationID:null,protocolID}, at='2026-10-21T08:00:00.000Z';
const fresh=()=>createDraft({id,ownerID,organizationID:null,at,snapshot:{protocol:{id:protocolID,organization_id:null,status:'draft',title:'Synthetic',updated_at:at},rooms:[],findings:[]}});
const key=(scope,id)=>JSON.stringify([scope.ownerID,scope.organizationID,scope.protocolID,id]);
// An atomic injected adapter: mutations become visible only when the transaction commits.
class AtomicStore {
 records=new Map();blobs=new Map();failCommit=false;tail=Promise.resolve();
 transaction(owner,action){
  const job=this.tail.catch(()=>{}).then(async()=>{
   const records=new Map(this.records),blobs=new Map(this.blobs);
   const tx={isOwnerDeleted:async()=>false,listOwner:async()=>[...records.values()].filter(row=>row.scope.ownerID===owner),getDraft:async(scope,id)=>records.get(key(scope,id))?.bytes??null,putDraft:async(scope,id,bytes)=>records.set(key(scope,id),{scope:{...scope},id,bytes}),deleteDraft:async(scope,id)=>records.delete(key(scope,id)),getBlob:async(scope,id)=>blobs.get(key(scope,id))??null,putBlob:async(scope,id,blob)=>blobs.set(key(scope,id),blob),deleteBlob:async(scope,id)=>blobs.delete(key(scope,id))};
   const value=await action(tx);if(this.failCommit)throw Error('synthetic transaction aborted');this.records=records;this.blobs=blobs;return value;
  });this.tail=job;return job;
 }
}

test('cold repository instance restores exact persisted metadata and photo bytes',async()=>{
 const store=new AtomicStore(),repo=new OutboxRepository(store,scope);let value=addFinding(addRoom(fresh(),{id:roomID,name:'Kitchen',condition:'ok',notes:''}),{id:findingID,roomID,title:'Window',description:'Synthetic',category:'Other',severity:'normal'});
 const blob=new Blob([new Uint8Array([137,80,78,71])],{type:'image/png'});
 value=addPhoto(value,{id:photoID,findingID,name:'synthetic.png',mime:'image/png',size:4,sha256:createHash('sha256').update(new Uint8Array([137,80,78,71])).digest('hex')});
 await repo.save(value,new Map([[photoID,blob]]),null);
 const reopened=new OutboxRepository(store,scope);assert.deepEqual(await reopened.load(),[value]);assert.deepEqual([...new Uint8Array(await (await reopened.photo(photoID)).arrayBuffer())],[137,80,78,71]);
});
test('aborted archive+photo transaction retains previous saved bytes and unsaved input',async()=>{
 const store=new AtomicStore(),repo=new OutboxRepository(store,scope),draft=fresh();await repo.save(draft,new Map(),null);const before=[...store.records.values()][0].bytes;
 const edited=addRoom(draft,{id:roomID,name:'Retained draft',condition:'ok',notes:''});store.failCommit=true;await assert.rejects(repo.save(edited,new Map(),0));assert.equal([...store.records.values()][0].bytes,before);assert.equal(edited.rooms[0].name,'Retained draft');assert.equal(store.blobs.size,0);
});
test('stale parallel saves reject without replacing latest saved record',async()=>{
 const store=new AtomicStore(),first=new OutboxRepository(store,scope),second=new OutboxRepository(store,scope);const draft=fresh();await first.save(draft,new Map(),null);
 const a=addRoom(draft,{id:roomID,name:'First',condition:'ok',notes:''}),b=addRoom(draft,{id:photoID,name:'Stale',condition:'ok',notes:''});const results=await Promise.allSettled([first.save(a,new Map(),0),second.save(b,new Map(),0)]);assert.equal(results.filter(result=>result.status==='fulfilled').length,1);assert.equal((await first.load())[0].rooms[0].name,'First');
});
test('corrupt or foreign stored record cannot be reset by later save',async()=>{
 const store=new AtomicStore(),repo=new OutboxRepository(store,scope),draft=fresh();await repo.save(draft,new Map(),null);const row=store.records.get(key(scope,id));row.bytes='{"schemaVersion":99}';await assert.rejects(repo.load());await assert.rejects(repo.save(draft,new Map(),0));assert.equal(store.records.get(key(scope,id)).bytes,'{"schemaVersion":99}');
});
test('account and workspace isolation prevents foreign loads, writes and photos',async()=>{
 const store=new AtomicStore(),repo=new OutboxRepository(store,scope),draft=fresh();await repo.save(draft,new Map(),null);const foreign=new OutboxRepository(store,{...scope,ownerID:photoID});assert.deepEqual(await foreign.load(),[]);await assert.rejects(foreign.save(draft,new Map(),null));assert.equal(await foreign.photo(photoID),null);assert.equal(decodeDraft(store.records.get(key(scope,id)).bytes,scope).ownerID,ownerID);
});
test('unacknowledged queued bytes cannot be deleted or overwritten and receipt retry is stable',async()=>{
 const store=new AtomicStore(),repo=new OutboxRepository(store,scope);const base=addRoom(fresh(),{id:roomID,name:'Kitchen',condition:'ok',notes:''}),queued=sealBatch(base,{operationID:photoID,at});await repo.save(queued,new Map(),null);await assert.rejects(repo.remove(id,queued.revision));await assert.rejects(repo.save(base,new Map(),queued.revision));assert.deepEqual((await repo.load())[0],queued);
});

test('photo blob bytes must match bounded metadata before archive commit',async()=>{
 const store=new AtomicStore(),repo=new OutboxRepository(store,scope);const base=addFinding(addRoom(fresh(),{id:roomID,name:'Kitchen',condition:'ok',notes:''}),{id:findingID,roomID,title:'Window',description:'Synthetic',category:'Other',severity:'normal'});const draft=addPhoto(base,{id:photoID,findingID,name:'synthetic.png',mime:'image/png',size:4,sha256:'a'.repeat(64)});await assert.rejects(repo.save(draft,new Map([[photoID,new Blob([new Uint8Array([1,2,3,4])],{type:'image/png'})]]),null));assert.equal(store.records.size,0);assert.equal(store.blobs.size,0);
});

test('another draft cannot reuse a photo identity to replace earlier saved bytes',async()=>{
 const store=new AtomicStore(),repo=new OutboxRepository(store,scope),make=(draftID,bytes)=>{const base=addFinding(addRoom({...fresh(),id:draftID},{id:roomID,name:'Kitchen',condition:'ok',notes:''}),{id:findingID,roomID,title:'Window',description:'Synthetic',category:'Other',severity:'normal'});return addPhoto(base,{id:photoID,findingID,name:'synthetic.png',mime:'image/png',size:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')});};
 const firstBytes=new Uint8Array([137,80,78,71]),secondBytes=new Uint8Array([1,2,3,4]);
 await repo.save(make(id,firstBytes),new Map([[photoID,new Blob([firstBytes],{type:'image/png'})]]),null);
 await assert.rejects(repo.save(make('88888888-8888-4888-8888-888888888888',secondBytes),new Map([[photoID,new Blob([secondBytes],{type:'image/png'})]]),null));
 assert.deepEqual([...new Uint8Array(await (await repo.photo(photoID)).arrayBuffer())],[137,80,78,71]);assert.equal((await repo.load()).length,1);
});
test('only explicit matching absent-receipt evidence permits an atomic queued rebase',async()=>{
 const store=new AtomicStore(),repo=new OutboxRepository(store,scope),queued=sealBatch(addRoom(fresh(),{id:roomID,name:'Kitchen',condition:'ok',notes:''}),{operationID:photoID,at});await repo.save(queued,new Map(),null);const freshBaseline=structuredClone(queued.baseline);freshBaseline.protocol.title='Reviewed current server title';
 const evidence={ownerID,protocolID,operationID:queued.operationID,payload:queued.batchPayload,exists:false,cancelled:true};
 await assert.rejects(repo.rebase(id,queued.revision,freshBaseline,{...evidence,cancelled:false},true));await assert.rejects(repo.rebase(id,queued.revision,freshBaseline,{...evidence,exists:true},true));await assert.rejects(repo.rebase(id,queued.revision,freshBaseline,evidence,false));await assert.rejects(repo.rebase(id,queued.revision,freshBaseline,{...evidence,operationID:findingID},true));
 const rebased=await repo.rebase(id,queued.revision,freshBaseline,evidence,true);assert.equal(rebased.state,'draft');assert.equal(rebased.operationID,null);assert.equal((await repo.load())[0].baseline.protocol.title,'Reviewed current server title');assert.deepEqual(rebased.rooms,queued.rooms);
});
