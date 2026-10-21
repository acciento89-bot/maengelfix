import test from 'node:test';
import assert from 'node:assert/strict';
import pg from 'pg';
import { randomUUID, createHash } from 'node:crypto';
import { mkdtemp, writeFile, readFile, rm, access } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { commitOfflineBatch, readInspectionSnapshot, readOfflineReceipt, cancelOfflineBatch } from './inspection-outbox.js';
import { createDraft, addRoom, addFinding, addPhoto, sealBatch } from '../client/src/inspection-outbox/core.js';

// Never run this fixture against a production or existing application database.
function testDatabase() {
 const value=process.env.MAENGELFIX_OUTBOX_TEST_DATABASE_URL;
 assert.ok(value,'Root must provide its disposable local test database URL');
 const url=new URL(value);assert.ok(['postgres:','postgresql:'].includes(url.protocol));assert.equal(url.hostname,'127.0.0.1');assert.equal(url.port,'25432');assert.match(decodeURIComponent(url.pathname.slice(1)),/^maengelfix_outbox_test_[a-z0-9_]+$/);assert.equal(url.search,'');return value;
}
const ownerID='11111111-1111-4111-8111-111111111111',foreignID='99999999-9999-4999-8999-999999999999',protocolID='22222222-2222-4222-8222-222222222222',roomID='44444444-4444-4444-8444-444444444444',findingID='55555555-5555-4555-8555-555555555555',photoID='66666666-6666-4666-8666-666666666666';
const at='2026-10-21T08:00:00.000Z';
async function fixture(run) {
 const connectionString=testDatabase(), schema='outbox_fixture_'+randomUUID().replaceAll('-','');
 const setup=new pg.Pool({connectionString,max:1});let pool;const directory=await mkdtemp(path.join(tmpdir(),'maengelfix-outbox-fixture-'));
 try {
  await setup.query(`CREATE SCHEMA ${schema}`);
  pool=new pg.Pool({connectionString,max:4,options:`-c search_path=${schema}`});
  await pool.query(`CREATE TABLE users(id text PRIMARY KEY); INSERT INTO users VALUES ('${ownerID}'),('${foreignID}');
   CREATE TABLE inspection_protocols(id text PRIMARY KEY,organization_id text,created_by text NOT NULL REFERENCES users(id),status text NOT NULL DEFAULT 'draft',title text NOT NULL,updated_at timestamptz NOT NULL);
   CREATE TABLE inspection_rooms(id text PRIMARY KEY,protocol_id text NOT NULL REFERENCES inspection_protocols(id),name text NOT NULL CHECK(name <> 'FAIL_TRANSACTION'),position integer NOT NULL,condition text NOT NULL,notes text,created_at timestamptz NOT NULL DEFAULT now());
   CREATE TABLE inspection_findings(id text PRIMARY KEY,protocol_id text NOT NULL REFERENCES inspection_protocols(id),room_id text REFERENCES inspection_rooms(id),created_by text NOT NULL REFERENCES users(id),title text NOT NULL,description text NOT NULL,category text NOT NULL,severity text NOT NULL,status text NOT NULL DEFAULT 'open',defect_case_id text,created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now());
   CREATE TABLE inspection_attachments(id text PRIMARY KEY,finding_id text NOT NULL REFERENCES inspection_findings(id),uploaded_by text NOT NULL REFERENCES users(id),original_name text NOT NULL CHECK(original_name <> 'FAIL_TRANSACTION.png'),stored_name text NOT NULL,mime_type text NOT NULL,size_bytes integer NOT NULL,created_at timestamptz NOT NULL DEFAULT now());
   CREATE TABLE inspection_offline_receipts(actor_id text NOT NULL REFERENCES users(id),operation_id text NOT NULL,protocol_id text NOT NULL REFERENCES inspection_protocols(id),payload_hash text NOT NULL,payload text NOT NULL,result jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(actor_id,operation_id));
   CREATE TABLE defect_cases(id text PRIMARY KEY);`);
  await pool.query('INSERT INTO inspection_protocols(id,created_by,title,updated_at) VALUES($1,$2,$3,$4)',[protocolID,ownerID,'Synthetic fixture',at]);
  const authorize=async(client,owner,protocol)=>{
   const result=await client.query('SELECT 1 FROM inspection_protocols WHERE id=$1 AND created_by=$2',[protocol,owner]);return result.rowCount===1;
  };
  const snapshot=await readInspectionSnapshot(pool,protocolID);
  const draft=()=>addFinding(addRoom(createDraft({id:randomUUID(),ownerID,organizationID:null,snapshot,at}),{id:roomID,name:'Kitchen',condition:'notice',notes:'Synthetic only'}),{id:findingID,roomID,title:'Window',description:'Synthetic observation',category:'Other',severity:'normal'});
  const make=()=>sealBatch(draft(),{operationID:randomUUID(),at});
  const commit=(queued,extra={})=>commitOfflineBatch({pool,ownerID,protocolID,payload:queued.batchPayload,photos:[],authorize,...extra});
  await run({pool,authorize,directory,draft,make,commit,snapshot});
 } finally {if(pool)await pool.end();await setup.query(`DROP SCHEMA IF EXISTS ${schema} CASCADE`);await setup.end();await rm(directory,{recursive:true,force:true});}
}
async function countRows(pool,table){return Number((await pool.query(`SELECT count(*) n FROM ${table}`)).rows[0].n);}
async function staged(directory,name='synthetic.png'){
 const bytes=Buffer.from([137,80,78,71,13,10,26,10]),file=path.join(directory,randomUUID()+'.png');await writeFile(file,bytes);
 return {localID:photoID,path:file,storedName:path.basename(file),name,mime:'image/png',size:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')};
}
async function absent(file){return access(file).then(()=>false,()=>true);}

test('real PostgreSQL concurrent retry commits one batch and returns stable receipt IDs',async()=>fixture(async({pool,make,commit})=>{
 const queued=make(),[first,second]=await Promise.all([commit(queued),commit(queued)]);assert.deepEqual(first,second);assert.equal(first.operationID,queued.operationID);assert.equal(first.ownerID,ownerID);assert.equal(first.payload,queued.batchPayload);assert.ok(first.result.rooms[roomID]);assert.ok(first.result.findings[findingID]);assert.equal(await countRows(pool,'inspection_rooms'),1);assert.equal(await countRows(pool,'inspection_findings'),1);assert.equal(await countRows(pool,'inspection_offline_receipts'),1);assert.equal(await countRows(pool,'defect_cases'),0);
 await pool.query("UPDATE inspection_protocols SET status='completed' WHERE id=$1",[protocolID]);assert.deepEqual(await commit(queued),first);
}));
test('same actor/key with altered body rejects; foreign actor and revoked entitlement write nothing',async()=>fixture(async({pool,make,commit,authorize})=>{
 const queued=make();await commit(queued);const changed=JSON.parse(queued.batchPayload);changed.rooms[0].name='Altered';await assert.rejects(commit(queued,{payload:JSON.stringify(changed)}));await assert.rejects(commit(queued,{ownerID:foreignID}));await assert.rejects(commit(queued,{authorize:async()=>false}));assert.equal(await countRows(pool,'inspection_rooms'),1);assert.equal(await countRows(pool,'inspection_offline_receipts'),1);
}));
test('actual changed child snapshot conflicts despite unchanged protocol timestamp',async()=>fixture(async({pool,make,commit})=>{
 const queued=make();await pool.query('INSERT INTO inspection_rooms(id,protocol_id,name,position,condition,notes) VALUES($1,$2,$3,0,$4,$5)',[randomUUID(),protocolID,'Concurrent room','ok','']);await assert.rejects(commit(queued));assert.equal(await countRows(pool,'inspection_findings'),0);assert.equal(await countRows(pool,'inspection_offline_receipts'),0);assert.equal(await countRows(pool,'inspection_rooms'),1);
}));
test('database failure after room+finding writes rolls back all rows and removes staged files',async()=>fixture(async({pool,draft,commit,directory})=>{
 const photo=await staged(directory,'FAIL_TRANSACTION.png');const value=addPhoto(draft(),{id:photoID,findingID,name:photo.name,mime:photo.mime,size:photo.size,sha256:photo.sha256});const queued=sealBatch(value,{operationID:randomUUID(),at});await assert.rejects(commit(queued,{photos:[photo]}));assert.equal(await countRows(pool,'inspection_rooms'),0);assert.equal(await countRows(pool,'inspection_findings'),0);assert.equal(await countRows(pool,'inspection_attachments'),0);assert.equal(await countRows(pool,'inspection_offline_receipts'),0);assert.equal(await absent(photo.path),true);
}));
test('matching retry discards redundant upload while retaining committed photo bytes',async()=>fixture(async({pool,draft,commit,directory})=>{
 const firstPhoto=await staged(directory);const value=addPhoto(draft(),{id:photoID,findingID,name:firstPhoto.name,mime:firstPhoto.mime,size:firstPhoto.size,sha256:firstPhoto.sha256});const queued=sealBatch(value,{operationID:randomUUID(),at});const first=await commit(queued,{photos:[firstPhoto]});assert.equal(await absent(firstPhoto.path),false);const retryPhoto=await staged(directory);assert.deepEqual(await commit(queued,{photos:[retryPhoto]}),first);assert.equal(await absent(retryPhoto.path),true);assert.equal(await absent(firstPhoto.path),false);assert.equal(await countRows(pool,'inspection_attachments'),1);assert.deepEqual([...await readFile(firstPhoto.path)],[137,80,78,71,13,10,26,10]);
}));
test('photo content mismatch rejects before any data/receipt commit and cleans temporary bytes',async()=>fixture(async({pool,draft,commit,directory})=>{
 const photo=await staged(directory);const queued=sealBatch(addPhoto(draft(),{id:photoID,findingID,name:photo.name,mime:photo.mime,size:photo.size,sha256:'a'.repeat(64)}),{operationID:randomUUID(),at});await assert.rejects(commit(queued,{photos:[photo]}));assert.equal(await countRows(pool,'inspection_rooms'),0);assert.equal(await countRows(pool,'inspection_offline_receipts'),0);assert.equal(await absent(photo.path),true);
}));

test('lost COMMIT acknowledgement recovers durable receipt without deleting committed photo',async()=>fixture(async({pool,draft,commit,directory})=>{
 const photo=await staged(directory),value=addPhoto(draft(),{id:photoID,findingID,name:photo.name,mime:photo.mime,size:photo.size,sha256:photo.sha256}),queued=sealBatch(value,{operationID:randomUUID(),at});
 let injected=false;
 const uncertainPool={query:(...args)=>pool.query(...args),connect:async()=>{const client=await pool.connect();return {query:async(...args)=>{const result=await client.query(...args);if(args[0]==='COMMIT'&&!injected){injected=true;throw Error('Synthetic lost acknowledgement AFTER real COMMIT');}return result;},release:()=>client.release()};}};
 let receipt,failure;try{receipt=await commit(queued,{pool:uncertainPool,photos:[photo]});}catch(error){failure=error;}assert.equal(injected,true,'The real COMMIT must complete before its acknowledgement is lost');assert.equal(await countRows(pool,'inspection_offline_receipts'),1,'Real receipt was durably committed');assert.equal(await countRows(pool,'inspection_attachments'),1,'Real attachment row was durably committed');assert.equal(await absent(photo.path),false,'Possibly committed photo must never be deleted');if(failure)throw failure;assert.equal(receipt.operationID,queued.operationID);
}));


test('authoritative receipt status binds actor operation and exact queued hash',async()=>fixture(async({pool,make,commit,authorize})=>{
 const queued=make(),payloadHash=createHash('sha256').update(queued.batchPayload).digest('hex');
 const args={pool,ownerID,protocolID,operationID:queued.operationID,payloadHash,authorize};
 assert.deepEqual(await readOfflineReceipt(args),{exists:false,ownerID,protocolID,operationID:queued.operationID,payloadHash});
 const receipt=await commit(queued);assert.deepEqual(await readOfflineReceipt(args),{exists:true,receipt});
 await assert.rejects(readOfflineReceipt({...args,payloadHash:'a'.repeat(64)}));await assert.rejects(readOfflineReceipt({...args,ownerID:foreignID}));await assert.rejects(readOfflineReceipt({...args,authorize:async()=>false}));
}));
test('receipt absence lookup waits for pending commit before reporting outcome',{timeout:10000},async()=>fixture(async({pool,make,commit,authorize})=>{
 const queued=make();let enter,release,entered=false;const reached=new Promise(resolve=>{enter=resolve;}),gate=new Promise(resolve=>{release=resolve;});
 const pausedPool={connect:async()=>{const client=await pool.connect();return{query:async(...args)=>{if(args[0]==='COMMIT'&&!entered){entered=true;enter();await gate;}return client.query(...args);},release:()=>client.release()};}};
 const writing=commit(queued,{pool:pausedPool});await reached;let settled=false;
 const lookup=readOfflineReceipt({pool,ownerID,protocolID,operationID:queued.operationID,payloadHash:createHash('sha256').update(queued.batchPayload).digest('hex'),authorize}).then(value=>{settled=true;return value;});
 try{await new Promise(resolve=>setImmediate(resolve));assert.equal(settled,false,'No absent receipt may escape while the same inspection commit remains unresolved');}finally{release();}
 const receipt=await writing;assert.deepEqual(await lookup,{exists:true,receipt});
}));


test('explicit cancelled operation tombstone prevents delayed old batch after absent lookup',async()=>fixture(async({pool,make,commit,authorize})=>{
 const queued=make(),payloadHash=createHash('sha256').update(queued.batchPayload).digest('hex'),args={pool,ownerID,protocolID,operationID:queued.operationID,payloadHash,authorize};assert.equal((await readOfflineReceipt(args)).exists,false);
 const cancelled=await cancelOfflineBatch(args);assert.equal(cancelled.exists,false);assert.equal(cancelled.cancelled,true);assert.deepEqual(await readOfflineReceipt(args),cancelled);assert.deepEqual(await cancelOfflineBatch(args),cancelled);
 await assert.rejects(commit(queued));assert.equal(await countRows(pool,'inspection_rooms'),0);assert.equal(await countRows(pool,'inspection_findings'),0);assert.equal(await countRows(pool,'inspection_offline_receipts'),1);
}));
test('cancel after committed batch returns real receipt instead of claiming absence',async()=>fixture(async({pool,make,commit,authorize})=>{
 const queued=make(),receipt=await commit(queued),args={pool,ownerID,protocolID,operationID:queued.operationID,payloadHash:createHash('sha256').update(queued.batchPayload).digest('hex'),authorize};assert.deepEqual(await cancelOfflineBatch(args),{exists:true,receipt});await assert.rejects(cancelOfflineBatch({...args,ownerID:foreignID}));await assert.rejects(cancelOfflineBatch({...args,payloadHash:'a'.repeat(64)}));assert.equal(await countRows(pool,'inspection_rooms'),1);
}));
