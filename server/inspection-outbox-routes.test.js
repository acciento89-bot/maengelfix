import test from 'node:test';
import assert from 'node:assert/strict';
import { registerOfflineInspectionRoutes } from './inspection-outbox-routes.js';
const ownerID='11111111-1111-4111-8111-111111111111',protocolID='22222222-2222-4222-8222-222222222222',operationID='33333333-3333-4333-8333-333333333333';
const path='/api/inspections/:protocolId/offline-batches';
function setup(overrides={}) {
 const routes=new Map(),calls={commit:[],read:[],access:[],cancel:[],upload:0};
 const app={post:(route,...handlers)=>routes.set('POST '+route,handlers),get:(route,...handlers)=>routes.set('GET '+route,handlers)};
 const auth=(req,res,next)=>req.user?next():res.status(401).json({error:'Sign in'});
 const privateProFeature=(req,res,next)=>req.planActive?next():res.status(402).json({error:'Existing entitlement required'});
 const deps={auth,privateProFeature,pool:{synthetic:true},upload:{array:(field,limit)=>(req,res,next)=>{calls.upload++;assert.equal(field,'photos');assert.equal(limit,250);next();}},inspectionAccess:async(actor,protocol)=>{calls.access.push({actor,protocol});return {id:protocolID,organization_id:null};},commitBatch:async args=>{calls.commit.push(args);assert.equal(await args.authorize({},ownerID,protocolID),true);return {operationID,ownerID,protocolID,payload:'synthetic only',result:{rooms:{},findings:{},photos:{}}};},cancelBatch:async args=>{calls.cancel.push(args);assert.equal(await args.authorize({},ownerID,protocolID),true);return {exists:false,cancelled:true,ownerID,protocolID,operationID,payloadHash:args.payloadHash};},readReceipt:async args=>{calls.read.push(args);return {exists:false,ownerID,protocolID,operationID,payloadHash:'a'.repeat(64)};},...overrides};
 registerOfflineInspectionRoutes(app,deps);
 async function request(method= 'POST',requestOverrides={},cancel=false) {
  const req={user:{id:ownerID},planActive:true,headers:{'content-length':'1024'},params:{protocolId:protocolID,operationId:operationID},query:{payloadHash:'a'.repeat(64)},body:{payload:'synthetic only',ownerID:'forged actor'},files:[],...requestOverrides};
  const res={code:200,body:null,status(code){this.code=code;return this;},json(body){this.body=body;return this;}};
  for(const handler of routes.get(method+' '+path+(cancel?'/:operationId/cancel':method==='GET'? '/:operationId':''))??[]){let next=false;await handler(req,res,()=>{next=true;});if(!next)break;}
  return res;
 }
 return {routes,calls,deps,request};
}
test('existing auth and private Pro gates run before multipart upload or data coordinator',async()=>{
 const {request,calls}=setup();assert.equal((await request('POST',{user:null})).code,401);assert.equal((await request('POST',{planActive:false})).code,402);assert.equal(calls.upload,0);assert.equal(calls.commit.length,0);
});
test('batch actor is authenticated user and authorization reuses existing inspection access',async()=>{
 const {request,calls}=setup();const response=await request();assert.equal(response.code,200);assert.equal(calls.commit.length,1);assert.equal(calls.commit[0].ownerID,ownerID);assert.equal(calls.commit[0].protocolID,protocolID);assert.equal(calls.commit[0].payload,'synthetic only');assert.deepEqual(calls.access,[{actor:ownerID,protocol:protocolID}]);assert.equal(response.body.receipt.operationID,operationID);
});
test('fresh foreign inspection authorization is denied instead of trusting a browser role or owner',async()=>{
 let allowed;const fixture=setup({inspectionAccess:async()=>null,commitBatch:async args=>{allowed=await args.authorize({},ownerID,protocolID);if(!allowed)throw Object.assign(Error('private internal detail'),{code:'identity'});}});const response=await fixture.request();assert.equal(allowed,false);assert.equal(response.code,403);assert.equal(JSON.stringify(response.body).includes('private internal detail'),false);
});
test('receipt lookup keeps existing gates and binds actor operation and expected body hash',async()=>{
 const {request,calls}=setup();assert.equal((await request('GET',{user:null})).code,401);assert.equal((await request('GET',{planActive:false})).code,402);const response=await request('GET');assert.equal(response.body.exists,false);assert.equal(calls.read.length,1);assert.equal(calls.read[0].ownerID,ownerID);assert.equal(calls.read[0].protocolID,protocolID);assert.equal(calls.read[0].operationID,operationID);assert.equal(calls.read[0].payloadHash,'a'.repeat(64));assert.equal(calls.upload,0);
});
test('unknown commit outcome is explicit retry state without reporting upload success or leaking internals',async()=>{
 const {request}=setup({commitBatch:async()=>{throw Object.assign(Error('SECRET_SQL_AND_FILE_PATH'),{code:'uncertain',operationID});}});const response=await request();assert.equal(response.code,503);assert.equal(response.body.code,'OUTCOME_UNKNOWN');assert.equal(response.body.operationID,operationID);assert.equal(JSON.stringify(response.body).includes('SECRET_SQL_AND_FILE_PATH'),false);assert.equal(Object.hasOwn(response.body,'receipt'),false);
});
test('baseline conflicts are distinct from unauthorized or invalid upload failures',async()=>{
 for(const [code,status]of [['conflict',409],['identity',403],['capacity',413],['invalid',400]]){const {request}=setup({commitBatch:async()=>{throw Object.assign(Error('INTERNAL'),{code});}});const response=await request();assert.equal(response.code,status);assert.equal(JSON.stringify(response.body).includes('INTERNAL'),false);}
});


test('explicit cancellation remains authenticated entitled and actor-bound without accepting uploads',async()=>{
 const {request,calls}=setup();assert.equal((await request('POST',{user:null},true)).code,401);assert.equal((await request('POST',{planActive:false},true)).code,402);const response=await request('POST',{body:{payloadHash:'a'.repeat(64),ownerID:'forged'}},true);assert.equal(response.body.cancelled,true);assert.equal(calls.cancel.length,1);assert.equal(calls.cancel[0].ownerID,ownerID);assert.equal(calls.cancel[0].operationID,operationID);assert.equal(calls.upload,0);
});
