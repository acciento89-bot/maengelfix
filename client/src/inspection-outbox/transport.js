import { validateDraft, acknowledgeBatch, OutboxError } from './core.js';
const fail=code=>{throw new OutboxError(code);};
const scope=draft=>({ownerID:draft.ownerID,organizationID:draft.organizationID,protocolID:draft.protocolID});
export async function sha256(blob) {return [...new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256',await blob.arrayBuffer()))].map(value=>value.toString(16).padStart(2,'0')).join('');}
export class OutboxTransport {
 constructor({fetcher=globalThis.fetch.bind(globalThis),isCurrentScope}) {this.fetcher=fetcher;this.isCurrentScope=isCurrentScope;}
 check(draft) {validateDraft(draft);if(draft.state!=='queued'||!this.isCurrentScope(scope(draft)))fail('identity');}
 async request(draft,url,options) {
  this.check(draft);let response;
  try{response=await this.fetcher(url,{credentials:'same-origin',...options});}catch{fail('uncertain');}
  if(!this.isCurrentScope(scope(draft)))fail('identity');
  if(!response.ok)fail(({401:'identity',403:'identity',402:'entitlement',409:'conflict',413:'capacity'})[response.status]??'uncertain');
  let body;try{body=await response.json();}catch{fail('uncertain');}
  if(!this.isCurrentScope(scope(draft)))fail('identity');return body;
 }
 async publish(draft,photos) {
  this.check(draft);const form=new FormData();form.append('payload',draft.batchPayload);form.append('photoIDs',JSON.stringify(draft.photos.map(photo=>photo.id)));
  if(!(photos instanceof Map)||photos.size!==draft.photos.length)fail('invalid');
  for(const photo of draft.photos) {
   const file=photos.get(photo.id);if(!(file instanceof Blob)||file.size!==photo.size||file.type!==photo.mime||await sha256(file)!==photo.sha256)fail('corrupt');
   this.check(draft);form.append('photos',file,photo.name);
  }
  const body=await this.request(draft,`/api/inspections/${draft.protocolID}/offline-batches`,{method:'POST',body:form});
  acknowledgeBatch(draft,body?.receipt,scope(draft));return body.receipt;
 }
 async cancel(draft) {
  this.check(draft);const payloadHash=await sha256(new Blob([draft.batchPayload]));this.check(draft);
  const body=await this.request(draft,`/api/inspections/${draft.protocolID}/offline-batches/${draft.operationID}/cancel`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({payloadHash})});
  if(body?.exists===true){acknowledgeBatch(draft,body.receipt,scope(draft));return body;}
  if(body?.exists!==false||body.cancelled!==true||body.ownerID!==draft.ownerID||body.protocolID!==draft.protocolID||body.operationID!==draft.operationID||body.payloadHash!==payloadHash)fail('identity');
  return {...body,payload:draft.batchPayload};
 }
 async receipt(draft) {
  this.check(draft);const payloadHash=await sha256(new Blob([draft.batchPayload]));this.check(draft);
  const body=await this.request(draft,`/api/inspections/${draft.protocolID}/offline-batches/${draft.operationID}?payloadHash=${payloadHash}`,{method:'GET'});
  if(body?.exists===true){acknowledgeBatch(draft,body.receipt,scope(draft));return body;}
  if(body?.exists!==false||body.ownerID!==draft.ownerID||body.protocolID!==draft.protocolID||body.operationID!==draft.operationID||body.payloadHash!==payloadHash)fail('identity');
  return {...body,payload:draft.batchPayload};
 }
}
