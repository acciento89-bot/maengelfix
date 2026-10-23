import test from 'node:test';
import assert from 'node:assert/strict';
import express from 'express';
import multer from 'multer';
import { once } from 'node:events';
import { OFFLINE_INSPECTION_UPLOAD_LIMITS, registerOfflineInspectionRoutes } from './inspection-outbox-routes.js';
const ceiling=1024*1024;
test('real multipart boundary accepts inclusive one MiB and rejects extra UTF8 bytes before coordinator',async()=>{
 const app=express(),received=[];
 registerOfflineInspectionRoutes(app,{
  auth:(req,_res,next)=>{req.user={id:'synthetic-owner'};next();},privateProFeature:(_req,_res,next)=>next(),
  upload:multer({storage:multer.memoryStorage(),limits:OFFLINE_INSPECTION_UPLOAD_LIMITS}),pool:null,
  inspectionAccess:async()=>null,commitBatch:async({payload})=>{received.push(payload);return {synthetic:true};}
 });
 app.use((error,_req,res,_next)=>res.status(error.code==='LIMIT_FIELD_VALUE'?413:500).json({code:error.code}));
 const server=app.listen(0,'127.0.0.1');await once(server,'listening');
 try {
  const url=`http://127.0.0.1:${server.address().port}/api/inspections/synthetic/offline-batches`;
  const raw='{"synthetic":"'+'x'.repeat(ceiling-16)+'"}';assert.equal(Buffer.byteLength(raw),ceiling);
  const send=async(payload)=>{const form=new FormData();form.append('payload',payload);form.append('photoIDs','[]');return fetch(url,{method:'POST',body:form});};
  assert.equal((await send(raw)).status,200);assert.deepEqual(received,[raw]);
  assert.equal((await send(raw+' ')).status,413);assert.equal(received.length,1);
  assert.equal((await send(raw.replace('x','€'))).status,413);assert.equal(received.length,1);
 } finally {server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
