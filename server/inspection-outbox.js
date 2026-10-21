// Isolated additive batch coordinator. Callers provide current authorization and staged uploads.
// No connection, route, migration or background job is started by importing this module.
import { randomUUID, createHash } from 'node:crypto';
import { readFile, stat, rm } from 'node:fs/promises';
import path from 'node:path';
import { createDraft, addRoom, addFinding, addPhoto, sealBatch, canonicalJSON, diffBaseline, OutboxError } from '../client/src/inspection-outbox/core.js';

const fail=code=>{throw new OutboxError(code);};
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const plain=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const json=value=>JSON.parse(JSON.stringify(value));
function requireID(value){if(typeof value!=='string'||!uuid.test(value))fail('identity');}
function exact(value,keys){if(!plain(value)||Object.keys(value).length!==keys.length||!keys.every(key=>Object.hasOwn(value,key)))fail('invalid');}

export async function readInspectionSnapshot(client,protocolID) {
 requireID(protocolID);
 const protocol=(await client.query('SELECT * FROM inspection_protocols WHERE id=$1',[protocolID])).rows[0];
 if(!protocol)fail('identity');
 const rooms=(await client.query('SELECT * FROM inspection_rooms WHERE protocol_id=$1 ORDER BY position,name,id',[protocolID])).rows;
 const findings=(await client.query(`SELECT f.*,r.name room_name,(SELECT count(*)::int FROM inspection_attachments a WHERE a.finding_id=f.id) attachment_count
  FROM inspection_findings f LEFT JOIN inspection_rooms r ON r.id=f.room_id WHERE f.protocol_id=$1 ORDER BY r.position,f.created_at,f.id`,[protocolID])).rows;
 return json({protocol,rooms,findings});
}
function decodePayload(raw,ownerID,protocolID) {
 requireID(ownerID);requireID(protocolID);
 if(typeof raw!=='string'||Buffer.byteLength(raw,'utf8')>1024*1024)fail('capacity');
 const body=JSON.parse(raw);
 exact(body,['version','operationID','protocolID','organizationID','baseline','rooms','findings','photos']);
 if(body.version!==1||body.protocolID!==protocolID||raw!==canonicalJSON(body))fail('invalid');
 requireID(body.operationID);
 let checked=createDraft({id:randomUUID(),ownerID,organizationID:body.organizationID,snapshot:body.baseline,at:new Date().toISOString()});
 if(checked.protocolID!==protocolID)fail('identity');
 for(const room of body.rooms)checked=addRoom(checked,room);
 for(const finding of body.findings)checked=addFinding(checked,finding);
 for(const photo of body.photos)checked=addPhoto(checked,photo);
 checked=sealBatch(checked,{operationID:body.operationID,at:checked.updatedAt});
 if(checked.batchPayload!==raw)fail('invalid');
 return body;
}
function magicMatches(bytes,mime) {
 if(mime==='image/png')return bytes.length>=8&&bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]));
 if(mime==='image/jpeg')return bytes.length>=3&&bytes[0]===255&&bytes[1]===216&&bytes[2]===255;
 return mime==='image/webp'&&bytes.length>=12&&bytes.toString('ascii',0,4)==='RIFF'&&bytes.toString('ascii',8,12)==='WEBP';
}
async function checkUploads(body,photos) {
 if(!Array.isArray(photos)||photos.length!==body.photos.length)fail('invalid');
 const keys=new Set();
 for(const file of photos) {
  if(!plain(file)||keys.has(file.localID))fail('invalid');keys.add(file.localID);
  const metadata=body.photos.find(item=>item.id===file.localID);
  if(!metadata||file.name!==metadata.name||file.mime!==metadata.mime||file.size!==metadata.size||typeof file.path!=='string'||typeof file.storedName!=='string'||path.basename(file.path)!==file.storedName||file.storedName.includes('/')||file.storedName.includes('\\'))fail('invalid');
  const info=await stat(file.path);if(!info.isFile()||info.size!==metadata.size||info.size>3*1024*1024)fail('capacity');
  const bytes=await readFile(file.path);
  if(bytes.length!==metadata.size||hash(bytes)!==metadata.sha256||!magicMatches(bytes,metadata.mime))fail('invalid');
 }
}
async function discardStaged(photos) {
 // Paths originate exclusively from the host's multipart staging adapter, never JSON payload.
 const errors=await Promise.allSettled((Array.isArray(photos)?photos:[]).filter(file=>typeof file?.path==='string').map(file=>rm(file.path,{force:true})));
 return errors.filter(result=>result.status==='rejected').map(result=>result.reason);
}
function receiptFrom(row) {return {operationID:row.operation_id,protocolID:row.protocol_id,ownerID:row.actor_id,payload:row.payload,result:row.result};}

async function recoverCommit({pool,ownerID,protocolID,body,payload,photos,authorize}) {
 const recovery=await pool.connect();
 try {
  await recovery.query('BEGIN');
  if(await authorize(recovery,ownerID,protocolID)!==true)fail('identity');
  // A fresh READ COMMITTED statement after acquiring the same lock observes a resolved original transaction.
  await recovery.query('SELECT id FROM inspection_protocols WHERE id=$1 FOR UPDATE',[protocolID]);
  const row=(await recovery.query('SELECT * FROM inspection_offline_receipts WHERE actor_id=$1 AND operation_id=$2',[ownerID,body.operationID])).rows[0];
  if(!row){await recovery.query('COMMIT');return null;}
  if(row.protocol_id!==protocolID||row.payload_hash!==hash(payload)||row.payload!==payload)fail('conflict');
  const receipt=receiptFrom(row);let used=0;
  for(const file of photos) {
   const attachmentID=receipt.result.photos[file.localID];
   const attachment=(await recovery.query('SELECT stored_name FROM inspection_attachments WHERE id=$1',[attachmentID])).rows[0];
   if(!attachment)fail('corrupt');
   if(attachment.stored_name===file.storedName)used++;
  }
  // The receipt is atomic. Mixed ownership is not evidence that any staged file is disposable.
  if(used!==0&&used!==photos.length)fail('corrupt');
  await recovery.query('COMMIT');return {receipt,duplicate:photos.length>0&&used===0};
 }catch(error){await recovery.query('ROLLBACK').catch(()=>{});throw error;}
 finally{recovery.release();}
}

export async function commitOfflineBatch({pool,ownerID,protocolID,payload,photos=[],authorize}) {
 let committed=false,duplicate=false,preserveStaged=false,client;
 try {
  const body=decodePayload(payload,ownerID,protocolID);
  if(typeof authorize!=='function')fail('identity');
  await checkUploads(body,photos);
  client=await pool.connect();
  let receipt;
  for(let attempt=0;attempt<3;attempt++) {
   let commitIssued=false;
   try {
    await client.query('BEGIN ISOLATION LEVEL SERIALIZABLE');
    // Authorization is repeated inside each transaction attempt. No actor/scope comes from payload.
    if(await authorize(client,ownerID,protocolID)!==true)fail('identity');
    const locked=(await client.query('SELECT id FROM inspection_protocols WHERE id=$1 FOR UPDATE',[protocolID])).rows[0];
    if(!locked)fail('identity');
    const prior=(await client.query('SELECT * FROM inspection_offline_receipts WHERE actor_id=$1 AND operation_id=$2',[ownerID,body.operationID])).rows[0];
    if(prior) {
     if(prior.protocol_id!==protocolID||prior.payload_hash!==hash(payload)||prior.payload!==payload)fail('conflict');
     receipt=receiptFrom(prior);duplicate=true;commitIssued=true;await client.query('COMMIT');break;
    }
    const current=await readInspectionSnapshot(client,protocolID);
    if(current.protocol.status!=='draft'||current.protocol.organization_id!==body.organizationID||diffBaseline(body.baseline,current).length)fail('conflict');
    const result={rooms:{},findings:{},photos:{}};
    const positions=current.rooms.map(room=>room.position).filter(Number.isSafeInteger);
    let position=positions.length?Math.max(...positions)+1:0;
    for(const room of body.rooms) {
     const serverID=randomUUID();
     await client.query('INSERT INTO inspection_rooms(id,protocol_id,name,position,condition,notes) VALUES($1,$2,$3,$4,$5,$6)',[serverID,protocolID,room.name,position++,room.condition,room.notes]);result.rooms[room.id]=serverID;
    }
    for(const finding of body.findings) {
     const serverID=randomUUID(),roomID=finding.roomID===null?null:result.rooms[finding.roomID]??finding.roomID;
     await client.query(`INSERT INTO inspection_findings(id,protocol_id,room_id,created_by,title,description,category,severity) VALUES($1,$2,$3,$4,$5,$6,$7,$8)`,[serverID,protocolID,roomID,ownerID,finding.title,finding.description,finding.category,finding.severity]);result.findings[finding.id]=serverID;
    }
    for(const photo of body.photos) {
     const serverID=randomUUID(),file=photos.find(item=>item.localID===photo.id);
     await client.query(`INSERT INTO inspection_attachments(id,finding_id,uploaded_by,original_name,stored_name,mime_type,size_bytes) VALUES($1,$2,$3,$4,$5,$6,$7)`,[serverID,result.findings[photo.findingID],ownerID,photo.name,file.storedName,photo.mime,photo.size]);result.photos[photo.id]=serverID;
    }
    await client.query('UPDATE inspection_protocols SET updated_at=now() WHERE id=$1',[protocolID]);
    const saved=(await client.query(`INSERT INTO inspection_offline_receipts(actor_id,operation_id,protocol_id,payload_hash,payload,result) VALUES($1,$2,$3,$4,$5,$6::jsonb) RETURNING *`,[ownerID,body.operationID,protocolID,hash(payload),payload,JSON.stringify(result)])).rows[0];
    commitIssued=true;await client.query('COMMIT');committed=true;receipt=receiptFrom(saved);break;
   } catch(error) {
    await client.query('ROLLBACK').catch(()=>{});
    if(commitIssued) {
     preserveStaged=true;
     try {
      const recovered=await recoverCommit({pool,ownerID,protocolID,body,payload,photos,authorize});
      if(recovered){receipt=recovered.receipt;duplicate=recovered.duplicate;committed=true;break;}
      // Lock acquisition plus authoritative absence proves no committed batch references these files.
      preserveStaged=false;
     }catch(recoveryError){
      const unknown=new OutboxError('uncertain');unknown.cause=recoveryError;unknown.operationID=body.operationID;throw unknown;
     }
     throw error;
    }
    if((error.code==='40001'||error.code==='40P01')&&attempt<2)continue;
    throw error;
   }
  }
  if(!receipt)fail('conflict');
  if(duplicate) {
   const cleanupErrors=await discardStaged(photos);
   if(cleanupErrors.length)throw new AggregateError(cleanupErrors,'Duplicate staged upload cleanup failed');
  }
  return receipt;
 } catch(error) {
  if(!committed&&!preserveStaged) {
   const cleanupErrors=await discardStaged(photos);
   if(cleanupErrors.length)error.stagedCleanupErrors=cleanupErrors;
  }
  throw error;
 } finally {client?.release();}
}

export async function readOfflineReceipt({pool,ownerID,protocolID,operationID,payloadHash,authorize}) {
 requireID(ownerID);requireID(protocolID);requireID(operationID);
 if(typeof payloadHash!=='string'||!/^[0-9a-f]{64}$/.test(payloadHash)||typeof authorize!=='function')fail('invalid');
 const client=await pool.connect();
 try {
  await client.query('BEGIN');
  if(await authorize(client,ownerID,protocolID)!==true)fail('identity');
  const protocol=(await client.query('SELECT id FROM inspection_protocols WHERE id=$1 FOR UPDATE',[protocolID])).rows[0];
  if(!protocol)fail('identity');
  const row=(await client.query('SELECT * FROM inspection_offline_receipts WHERE actor_id=$1 AND operation_id=$2',[ownerID,operationID])).rows[0];
  if(row&&(row.protocol_id!==protocolID||row.payload_hash!==payloadHash))fail('conflict');
  const result=row?(row.result.cancelled===true?{exists:false,cancelled:true,ownerID,protocolID,operationID,payloadHash}:{exists:true,receipt:receiptFrom(row)}):{exists:false,ownerID,protocolID,operationID,payloadHash};
  await client.query('COMMIT');return result;
 }catch(error){await client.query('ROLLBACK').catch(()=>{});throw error;}
 finally{client.release();}
}


export async function cancelOfflineBatch({pool,ownerID,protocolID,operationID,payloadHash,authorize}) {
 requireID(ownerID);requireID(protocolID);requireID(operationID);
 if(typeof payloadHash!=='string'||!/^[0-9a-f]{64}$/.test(payloadHash)||typeof authorize!=='function')fail('invalid');
 const client=await pool.connect();let commitIssued=false;
 try {
  await client.query('BEGIN');
  if(await authorize(client,ownerID,protocolID)!==true)fail('identity');
  const protocol=(await client.query('SELECT id FROM inspection_protocols WHERE id=$1 FOR UPDATE',[protocolID])).rows[0];if(!protocol)fail('identity');
  let row=(await client.query('SELECT * FROM inspection_offline_receipts WHERE actor_id=$1 AND operation_id=$2',[ownerID,operationID])).rows[0];
  if(row&&(row.protocol_id!==protocolID||row.payload_hash!==payloadHash))fail('conflict');
  if(!row)row=(await client.query("INSERT INTO inspection_offline_receipts(actor_id,operation_id,protocol_id,payload_hash,payload,result) VALUES($1,$2,$3,$4,'',$5::jsonb) RETURNING *",[ownerID,operationID,protocolID,payloadHash,JSON.stringify({cancelled:true})])).rows[0];
  const result=row.result.cancelled===true?{exists:false,cancelled:true,ownerID,protocolID,operationID,payloadHash}:{exists:true,receipt:receiptFrom(row)};
  commitIssued=true;await client.query('COMMIT');return result;
 }catch(error){await client.query('ROLLBACK').catch(()=>{});if(commitIssued){const uncertain=new OutboxError('uncertain');uncertain.operationID=operationID;throw uncertain;}throw error;}
 finally{client.release();}
}
