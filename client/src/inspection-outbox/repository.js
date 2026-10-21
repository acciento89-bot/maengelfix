import { decodeDraft, encodeDraft, OutboxError, MAX_DRAFT_PHOTO_BYTES, rebaseDraft } from './core.js';
const fail = code => { throw new OutboxError(code); };
const sameScope = (a,b) => a.ownerID === b.ownerID && a.organizationID === b.organizationID && a.protocolID === b.protocolID;
const scopeOf = draft => ({ownerID:draft.ownerID,organizationID:draft.organizationID,protocolID:draft.protocolID});
async function verifyPhoto(blob,photo) {
 if (!(blob instanceof Blob) || blob.size !== photo.size || blob.type !== photo.mime) fail('corrupt');
 const digest = await globalThis.crypto.subtle.digest('SHA-256',await blob.arrayBuffer());
 const hex = [...new Uint8Array(digest)].map(value=>value.toString(16).padStart(2,'0')).join('');
 if(hex !== photo.sha256) fail('corrupt');
}
export class OutboxRepository {
 constructor(storage,scope) {
  // Validate the same identity boundary used by the core without creating data.
  if(!scope || !/^[0-9a-f-]{36}$/i.test(scope.ownerID) || !/^[0-9a-f-]{36}$/i.test(scope.protocolID) || !(scope.organizationID === null || /^[0-9a-f-]{36}$/i.test(scope.organizationID))) fail('identity');
  this.storage=storage;this.scope=Object.freeze({...scope});
 }
 async ownerSnapshot() {
  const rows = await this.storage.transaction(this.scope.ownerID,async tx=>{
   if(await tx.isOwnerDeleted())fail('identity');
   const result=[];
   for(const row of await tx.listOwner()) {
    if(row.scope.ownerID !== this.scope.ownerID) fail('identity');
    const draft=decodeDraft(row.bytes,row.scope);if(row.id !== draft.id) fail('identity');
    const blobs=[];for(const photo of draft.photos) blobs.push({photo,blob:await tx.getBlob(row.scope,photo.id)});
    result.push({...row,draft,blobs});
   }
   return result;
  });
  for(const row of rows) for(const {photo,blob} of row.blobs) await verifyPhoto(blob,photo);
  return rows;
 }
 async load() {return (await this.ownerSnapshot()).filter(row=>sameScope(row.scope,this.scope)).map(row=>row.draft);}
 async photos(draftID) {
  const rows=await this.ownerSnapshot(),row=rows.find(value=>sameScope(value.scope,this.scope)&&value.id===draftID);
  if(!row)fail('identity');
  return new Map(row.blobs.map(value=>[value.photo.id,value.blob]));
 }
 async photo(photoID) {
  const rows=await this.ownerSnapshot();
  for(const row of rows) if(sameScope(row.scope,this.scope)) {
   const found=row.blobs.find(item=>item.photo.id===photoID);if(found)return found.blob;
  }
  return null;
 }
 async save(draft,photos=new Map(),expectedRevision=null) {
  const bytes=encodeDraft(draft),next=decodeDraft(bytes,this.scope);
  if(!sameScope(scopeOf(next),this.scope)) fail('identity');
  const uploaded=new Map(photos);
  for(const [photoID,blob] of uploaded) {
   const metadata=next.photos.find(item=>item.id===photoID);if(!metadata)fail('identity');await verifyPhoto(blob,metadata);
  }
  const preflight=await this.ownerSnapshot();
  await this.storage.transaction(this.scope.ownerID,async tx=>{
   if(await tx.isOwnerDeleted())fail('identity');
   const rows=await tx.listOwner();
   if(rows.length!==preflight.length || rows.some(row=>!preflight.some(old=>sameScope(old.scope,row.scope)&&old.id===row.id&&old.bytes===row.bytes)))fail('conflict');
   const previous=await tx.getDraft(this.scope,next.id);
   const old=previous===null?null:decodeDraft(previous,this.scope);
   if(old===null ? expectedRevision!==null : old.revision!==expectedRevision)fail('conflict');
   if(old && (next.revision<=old.revision && bytes!==previous))fail('conflict');
   // A queued operation must survive ambiguous outcomes. Only its exact receipt may advance it.
   if(old?.state==='queued' && !(next.state==='queued'&&next.batchPayload===old.batchPayload || next.state==='acknowledged'&&next.batchPayload===old.batchPayload))fail('conflict');
   if(old?.state==='acknowledged' && bytes!==previous)fail('conflict');
   const others=rows.filter(row=>!(sameScope(row.scope,this.scope)&&row.id===next.id));
   if(others.length>=10)fail('capacity');
   for(const row of others)if(sameScope(row.scope,this.scope)) {
    const other=decodeDraft(row.bytes,row.scope);
    if(next.photos.some(photo=>other.photos.some(saved=>saved.id===photo.id)))fail('identity');
   }
   let ownerBytes=next.photos.reduce((sum,item)=>sum+item.size,0);
   for(const row of others)ownerBytes+=decodeDraft(row.bytes,row.scope).photos.reduce((sum,item)=>sum+item.size,0);
   if(ownerBytes>50*1024*1024 || next.photos.reduce((sum,item)=>sum+item.size,0)>MAX_DRAFT_PHOTO_BYTES)fail('capacity');
   for(const metadata of next.photos) {
    const blob=uploaded.get(metadata.id)??await tx.getBlob(this.scope,metadata.id);
    if(!blob || blob.size!==metadata.size || blob.type!==metadata.mime)fail('corrupt');
    if(!uploaded.has(metadata.id) && !old?.photos.some(item=>JSON.stringify(item)===JSON.stringify(metadata)))fail('corrupt');
    if(uploaded.has(metadata.id))await tx.putBlob(this.scope,metadata.id,blob);
   }
   for(const photo of old?.photos??[])if(!next.photos.some(item=>item.id===photo.id))await tx.deleteBlob(this.scope,photo.id);
   await tx.putDraft(this.scope,next.id,bytes);
  });
  return next;
 }
 async rebase(draftID,expectedRevision,snapshot,evidence,confirmed) {
  await this.ownerSnapshot();
  return this.storage.transaction(this.scope.ownerID,async tx=>{
   if(await tx.isOwnerDeleted())fail('identity');
   const bytes=await tx.getDraft(this.scope,draftID);if(bytes===null)fail('conflict');
   const current=decodeDraft(bytes,this.scope);
   if(current.revision!==expectedRevision||current.state!=='queued'||!evidence||evidence.exists!==false||evidence.cancelled!==true||evidence.ownerID!==current.ownerID||evidence.protocolID!==current.protocolID||evidence.operationID!==current.operationID||evidence.payload!==current.batchPayload||confirmed!==true)fail('conflict');
   const next=rebaseDraft(current,snapshot,{...this.scope,receiptAbsent:true,operationCancelled:true,confirmed:true});
   await tx.putDraft(this.scope,current.id,encodeDraft(next));return next;
  });
 }
 async remove(draftID,expectedRevision) {
  await this.ownerSnapshot();
  return this.storage.transaction(this.scope.ownerID,async tx=>{
   if(await tx.isOwnerDeleted())fail('identity');
   const bytes=await tx.getDraft(this.scope,draftID);if(bytes===null)return false;
   const draft=decodeDraft(bytes,this.scope);if(draft.revision!==expectedRevision || draft.state==='queued')fail('conflict');
   for(const photo of draft.photos)await tx.deleteBlob(this.scope,photo.id);
   await tx.deleteDraft(this.scope,draftID);return true;
  });
 }
}

const key=(scope,id)=>JSON.stringify([scope.ownerID,scope.organizationID,scope.protocolID,id]);
function request(input) {return new Promise((resolve,reject)=>{input.onsuccess=()=>resolve(input.result);input.onerror=()=>reject(input.error);});}
// A dedicated database contains only the new feature. No auth tokens or API cache.
export class IndexedDBOutboxStorage {
 constructor(indexedDB=globalThis.indexedDB) {this.indexedDB=indexedDB;this.opening=null;}
 open() {
  if(!this.opening)this.opening=new Promise((resolve,reject)=>{
   const opening=this.indexedDB.open('maengelfix-inspection-outbox',2);
   opening.onupgradeneeded=()=>{
    const database=opening.result;
    for(const name of ['drafts','photos','owners'])if(!database.objectStoreNames.contains(name))database.createObjectStore(name);
   };
   opening.onsuccess=()=>resolve(opening.result);opening.onerror=()=>reject(opening.error);opening.onblocked=()=>reject(new OutboxError('conflict'));
  });
  return this.opening;
 }
 async transaction(ownerID,action) {
  const database=await this.open();
  return new Promise((resolve,reject)=>{
   const transaction=database.transaction(['drafts','photos','owners'],'readwrite');
   const records=transaction.objectStore('drafts'),photos=transaction.objectStore('photos'),owners=transaction.objectStore('owners');let value;let cause;
   const check=scope=>{if(scope.ownerID!==ownerID)fail('identity');};
   const ownerKey=encoded=>{try{const values=JSON.parse(encoded);return Array.isArray(values)?values[0]:null;}catch{return null;}};
   const removeOwned=store=>new Promise((resolve,reject)=>{
    const scan=store.openCursor();scan.onerror=()=>reject(scan.error);
    scan.onsuccess=async()=>{const cursor=scan.result;if(!cursor){resolve();return;}try{if(ownerKey(cursor.key)===ownerID)await request(cursor.delete());cursor.continue();}catch(error){reject(error);}};
   });
   const api={
    isOwnerDeleted:async()=>((await request(owners.get(ownerID)))?.deleted===true),
    markOwnerDeleted:async()=>request(owners.put({deleted:true},ownerID)),
    deleteOwnerData:async()=>{await removeOwned(records);await removeOwned(photos);},
    listOwner:async()=>{const keys=await request(records.getAllKeys()),rows=await request(records.getAll());return rows.filter((_row,index)=>ownerKey(keys[index])===ownerID);},
    getDraft:async(scope,id)=>{check(scope);return (await request(records.get(key(scope,id))))?.bytes??null;},
    putDraft:async(scope,id,bytes)=>{check(scope);return request(records.put({scope:{...scope},id,bytes},key(scope,id)));},
    deleteDraft:async(scope,id)=>{check(scope);return request(records.delete(key(scope,id)));},
    getBlob:async(scope,id)=>{check(scope);return (await request(photos.get(key(scope,id))))??null;},
    putBlob:async(scope,id,blob)=>{check(scope);return request(photos.put(blob,key(scope,id)));},
    deleteBlob:async(scope,id)=>{check(scope);return request(photos.delete(key(scope,id)));},
   };
   transaction.oncomplete=()=>resolve(value);transaction.onabort=()=>reject(cause??transaction.error??new OutboxError('corrupt'));transaction.onerror=()=>{cause??=transaction.error;};
   Promise.resolve().then(()=>action(api)).then(result=>{value=result;}).catch(error=>{cause=error;try{transaction.abort();}catch{reject(error);}});
  });
 }
 async purgeOwner(ownerID) {return purgeOutboxOwner(this,ownerID);}
}
export async function purgeOutboxOwner(storage,ownerID) {
 if(typeof ownerID!=='string'||!(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i).test(ownerID))fail('identity');
 const owner=ownerID.toLowerCase();
 return storage.transaction(owner,async tx=>{await tx.markOwnerDeleted();await tx.deleteOwnerData();});
}
