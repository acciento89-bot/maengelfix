import { rm } from 'node:fs/promises';
import { commitOfflineBatch, readOfflineReceipt, cancelOfflineBatch } from './inspection-outbox.js';
function failure(res,error) {
 const codes={identity:[403,'ACCESS_DENIED'],conflict:[409,'BASELINE_CONFLICT'],capacity:[413,'OUTBOX_LIMIT'],invalid:[400,'INVALID_BATCH'],future:[400,'INVALID_BATCH'],corrupt:[400,'INVALID_BATCH'],uncertain:[503,'OUTCOME_UNKNOWN']};
 const [status,code]=codes[error.code]??[500,'OUTBOX_ERROR'];
 return res.status(status).json({code,error:code==='OUTCOME_UNKNOWN'?'Der Übertragungsstatus ist unklar. Bitte denselben Ausgang erneut prüfen.':'Der lokale Ausgang konnte nicht übernommen werden. Deine lokalen Daten bleiben erhalten.',...(code==='OUTCOME_UNKNOWN'&&error.operationID?{operationID:error.operationID}:{})});
}
export function limitOfflineUpload(req,res,next) {
 const length=req.headers?.['content-length'];
 if(typeof length!=='string'||!(/^[1-9]\d*$/).test(length)||req.headers?.['transfer-encoding'])return res.status(411).json({code:'UPLOAD_LENGTH_REQUIRED',error:'Die Übertragung benötigt eine bekannte Dateigröße.'});
 if(!Number.isSafeInteger(Number(length))||Number(length)>22*1024*1024)return res.status(413).json({code:'OUTBOX_LIMIT',error:'Der lokale Ausgang ist für eine Übertragung zu groß.'});
 return next();
}
export function registerOfflineInspectionRoutes(app,{auth,privateProFeature,upload,pool,inspectionAccess,commitBatch=commitOfflineBatch,readReceipt=readOfflineReceipt,cancelBatch=cancelOfflineBatch}) {
 const authorizeFor=(ownerID,protocolID)=>async(_client,actor,protocol)=>{
  if(actor!==ownerID||protocol!==protocolID)return false;
  const record=await inspectionAccess(ownerID,protocolID);return record?.id===protocolID;
 };
 app.post('/api/inspections/:protocolId/offline-batches',auth,privateProFeature,limitOfflineUpload,upload.array('photos',250),async(req,res)=>{
  let coordinatorStarted=false;
  try {
   const ids=req.body?.photoIDs===undefined?[]:JSON.parse(req.body.photoIDs);
   if(!Array.isArray(ids)||ids.length!==(req.files??[]).length)throw Object.assign(Error(),{code:'invalid'});
   const photos=(req.files??[]).map((file,index)=>({localID:ids[index],path:file.path,storedName:file.filename,name:file.originalname,mime:file.mimetype,size:file.size}));
   const ownerID=req.user.id,protocolID=req.params.protocolId;
   coordinatorStarted=true;
   const receipt=await commitBatch({pool,ownerID,protocolID,payload:req.body?.payload,photos,authorize:authorizeFor(ownerID,protocolID)});
   return res.json({receipt});
  }catch(error){
   // Once delegated, the coordinator owns cleanup, including unresolved COMMIT outcomes.
   if(!coordinatorStarted)await Promise.allSettled((req.files??[]).map(file=>rm(file.path,{force:true})));
   return failure(res,error);
  }
 });
 app.post('/api/inspections/:protocolId/offline-batches/:operationId/cancel',auth,privateProFeature,async(req,res)=>{
  try {
   const ownerID=req.user.id,protocolID=req.params.protocolId;
   return res.json(await cancelBatch({pool,ownerID,protocolID,operationID:req.params.operationId,payloadHash:req.body?.payloadHash,authorize:authorizeFor(ownerID,protocolID)}));
  }catch(error){return failure(res,error);}
 });
 app.get('/api/inspections/:protocolId/offline-batches/:operationId',auth,privateProFeature,async(req,res)=>{
  try {
   const ownerID=req.user.id,protocolID=req.params.protocolId;
   return res.json(await readReceipt({pool,ownerID,protocolID,operationID:req.params.operationId,payloadHash:req.query.payloadHash,authorize:authorizeFor(ownerID,protocolID)}));
  }catch(error){return failure(res,error);}
 });
}
