import { useEffect, useMemo, useRef, useState } from 'react';
import { createDraft, addRoom, addFinding, addPhoto, validateDraft, sealBatch, acknowledgeBatch, diffBaseline } from './core.js';
import { IndexedDBOutboxStorage, OutboxRepository } from './repository.js';
import { OutboxTransport, sha256 } from './transport.js';
import './outbox.css';

export const outboxStorage = new IndexedDBOutboxStorage();
const id=()=>crypto.randomUUID();
const stamp=()=>new Date().toISOString();
const emptyRoom={name:'',condition:'ok',notes:''};
const emptyFinding={roomID:'',title:'',description:'',category:'Sonstiges',severity:'normal'};
const sameFields=(value,baseline)=>Object.keys(baseline).every(key=>value[key]===baseline[key]);
function updated(draft,changes) {return validateDraft({...draft,...changes,revision:draft.revision+1,updatedAt:stamp()});}
function valid(action) {try{action();return true;}catch{return false;}}
function Photo({photo,blob,onRemove,editable,l}) {
 const [url,setURL]=useState(null);
 useEffect(()=>{if(!blob){setURL(null);return;}const objectURL=URL.createObjectURL(blob);setURL(objectURL);return()=>URL.revokeObjectURL(objectURL);},[blob]);
 return <figure className="outboxPhoto">{url?<img src={url} alt={photo.name}/>:<span>{l('Foto wird geprüft …','Checking photo …')}</span>}<figcaption>{photo.name} · {Math.ceil(photo.size/1024)} KB</figcaption>{editable&&<button type="button" onClick={onRemove}>{l('Lokales Foto entfernen','Remove local photo')}</button>}</figure>;
}

export function InspectionOutbox({ownerID,initialSnapshot,readCurrent,onClose,onAcknowledged,isCurrentOwner}) {
 const [language,setLanguage]=useState(()=>navigator.language.startsWith('de')?'de':'en');
 const l=(german,english)=>language==='de'?german:english;
 const scope=useMemo(()=>({ownerID,organizationID:initialSnapshot.protocol.organization_id,protocolID:initialSnapshot.protocol.id}),[ownerID,initialSnapshot.protocol.organization_id,initialSnapshot.protocol.id]);
 const repository=useMemo(()=>new OutboxRepository(outboxStorage,scope),[scope]);
 const alive=useRef(true),busyRef=useRef(false),identity=useRef(isCurrentOwner);identity.current=isCurrentOwner;
 const current=()=>alive.current&&identity.current();
 const transport=useMemo(()=>new OutboxTransport({isCurrentScope:value=>current()&&value.ownerID===scope.ownerID&&value.organizationID===scope.organizationID&&value.protocolID===scope.protocolID}),[scope]);
 const [gallery,setGallery]=useState(new Map());
 const [drafts,setDrafts]=useState([]),[selectedID,setSelectedID]=useState(null),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[blocked,setBlocked]=useState(false),[accessFailed,setAccessFailed]=useState(false),[error,setError]=useState(null);
 const [room,setRoom]=useState(emptyRoom),[roomEdit,setRoomEdit]=useState(null),[finding,setFinding]=useState(emptyFinding),[findingEdit,setFindingEdit]=useState(null),[pendingFiles,setPendingFiles]=useState(null),[review,setReview]=useState(null),[confirmed,setConfirmed]=useState(false);
 const [roomBase,setRoomBase]=useState(emptyRoom),[findingBase,setFindingBase]=useState(emptyFinding);
 const draft=drafts.find(value=>value.id===selectedID),editable=draft?.state==='draft'&&!blocked&&!busy;
 const roomDirty=!sameFields(room,roomBase),findingDirty=!sameFields(finding,findingBase);
 const hasUnsaved=roomDirty||findingDirty||Boolean(pendingFiles);
 const message=cause=>({identity:l('Die aktuelle Anmeldung oder der Zugriff ist nicht mehr verfügbar. Schließe diese Ansicht.','The current account or access is unavailable. Close this view.'),entitlement:l('Der bestehende Tarif erlaubt die Übertragung gerade nicht. Lokale Daten bleiben erhalten.','The current plan does not permit publishing. Local data is retained.'),capacity:l('Eine Höchstgrenze wurde erreicht: 20 Räume, 50 Feststellungen, 5 Fotos je Feststellung, 3 MB je Foto, 20 MB je Entwurf, 10 Entwürfe / 50 MB je Konto.','A limit was reached: 20 rooms, 50 findings, 5 photos per finding, 3 MB per photo, 20 MB per draft, 10 drafts / 50 MB per account.'),conflict:l('Der gespeicherte oder serverseitige Stand hat sich geändert. Vergleiche die aktuellen Angaben; der Ausgang bleibt erhalten.','The saved or server record changed. Review the current information; the outbox is retained.'),uncertain:l('Der Übertragungsstatus ist unklar. Prüfe denselben Ausgang erneut; es wird kein neuer Vorgang automatisch angelegt.','The upload outcome is unknown. Check the same outbox again; a new operation is never created automatically.'),corrupt:l('Die lokalen Daten oder Fotos konnten nicht sicher gelesen werden. Sie bleiben erhalten.','Local data or photos could not be read safely. They are retained.'),future:l('Die lokalen Daten haben ein unbekanntes Format und bleiben erhalten.','Local data has an unknown format and is retained.'),invalid:l('Bitte prüfe Pflichtfelder, Formate und Höchstlängen.','Check required fields, formats and maximum lengths.')}[cause?.code]??l('Speichern oder Laden fehlgeschlagen. Gespeicherte Daten und deine Eingaben bleiben erhalten.','Saving or loading failed. Saved data and your input are retained.'));
 async function reload(preferred=selectedID) {
  const values=await repository.load();if(!current())return;setDrafts(values);setSelectedID(values.some(value=>value.id===preferred)?preferred:values.at(-1)?.id??null);setBlocked(false);
 }
 useEffect(()=>{let active=true;alive.current=true;setLoading(true);setDrafts([]);setSelectedID(null);repository.load().then(values=>{if(active&&current()){setDrafts(values);setSelectedID(values.at(-1)?.id??null);setBlocked(false);}}).catch(cause=>{if(active&&current()){setBlocked(true);setError(message(cause));}}).finally(()=>{if(active&&current())setLoading(false);});return()=>{active=false;alive.current=false;};},[repository]);
 useEffect(()=>{let active=true;setGallery(new Map());if(draft)repository.photos(draft.id).then(values=>{if(active&&current())setGallery(values);}).catch(cause=>{if(active&&current()){setError(message(cause));setBlocked(true);}});return()=>{active=false;};},[repository,draft?.id,draft?.revision]);
 useEffect(()=>{if(!hasUnsaved)return;const warn=event=>{event.preventDefault();event.returnValue='';};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[hasUnsaved]);
 async function run(action) {
  if(busyRef.current||!current()||accessFailed)return false;
  busyRef.current=true;setBusy(true);setError(null);
  try{const preferred=await action();if(!current())return false;await reload(typeof preferred==='string'?preferred:selectedID);return true;}
  catch(cause){if(current()){setError(message(cause));if(cause?.code==='identity')setAccessFailed(true);if(cause?.code==='corrupt'||cause?.code==='future')setBlocked(true);}return false;}
  finally{busyRef.current=false;if(current())setBusy(false);}
 }
 const allowDiscard=(dirty=hasUnsaved)=>!dirty||confirm(l('Noch nicht gespeicherte Eingaben verwerfen? Bereits gespeicherte Entwürfe bleiben erhalten.','Discard unsaved input? Saved drafts are kept.'));
 const close=()=>{if(allowDiscard())onClose();};
 const clearRoom=()=>{setRoom(emptyRoom);setRoomBase(emptyRoom);setRoomEdit(null);};
 const clearFinding=()=>{setFinding(emptyFinding);setFindingBase(emptyFinding);setFindingEdit(null);};
 const resetForms=()=>{clearRoom();clearFinding();setPendingFiles(null);setReview(null);setConfirmed(false);};
 const switchDraft=next=>{if(next===selectedID||!allowDiscard())return;resetForms();setSelectedID(next);};
 const beginRoomEdit=value=>{if(roomEdit===value.id||!allowDiscard())return;resetForms();const baseline={name:value.name,condition:value.condition,notes:value.notes};setRoomEdit(value.id);setRoom(baseline);setRoomBase(baseline);};
 const beginFindingEdit=value=>{if(findingEdit===value.id||!allowDiscard())return;resetForms();const baseline={roomID:value.roomID??'',title:value.title,description:value.description,category:value.category,severity:value.severity};setFindingEdit(value.id);setFinding(baseline);setFindingBase(baseline);};
 async function newDraft() {
  if(!allowDiscard())return;
  const okay=await run(async()=>{const snapshot=await readCurrent();if(!current())throw Object.assign(Error(),{code:'identity'});const value=createDraft({id:id(),ownerID,organizationID:scope.organizationID,snapshot,at:stamp()});await repository.save(value,new Map(),null);return value.id;});if(okay)resetForms();
 }
 function roomCandidate() {
  if(!draft||roomEdit&&!draft.rooms.some(value=>value.id===roomEdit))throw Error();return roomEdit?updated(draft,{rooms:draft.rooms.map(value=>value.id===roomEdit?{id:roomEdit,...room,name:room.name.trim()}:value)}):updated(addRoom(draft,{id:id(),...room}),{});
 }
 function findingCandidate() {
  if(!draft||findingEdit&&!draft.findings.some(value=>value.id===findingEdit))throw Error();const value={...finding,roomID:finding.roomID||null,title:finding.title.trim()};return findingEdit?updated(draft,{findings:draft.findings.map(item=>item.id===findingEdit?{id:findingEdit,...value}:item)}):updated(addFinding(draft,{id:id(),...value}),{});
 }
 async function saveRoom(event){event.preventDefault();const okay=await run(async()=>{await repository.save(roomCandidate(),new Map(),draft.revision);});if(okay)clearRoom();}
 async function saveFinding(event){event.preventDefault();const okay=await run(async()=>{await repository.save(findingCandidate(),new Map(),draft.revision);});if(okay)clearFinding();}
 async function removeLocal(changes) {
  if(!confirm(l('Diese Angabe nur aus dem lokalen Entwurf entfernen?','Remove this item only from the local draft?')))return;
  await run(async()=>{await repository.save(updated(draft,changes),new Map(),draft.revision);});
 }
 async function captureFiles(findingID,files) {
  if(busyRef.current||!current())return;
  if(pendingFiles&&!(pendingFiles.findingID===findingID&&pendingFiles.files===files)&&!confirm(l('Die noch nicht gespeicherte Fotoauswahl ersetzen?','Replace the unsaved photo selection?')))return;
  const pending={findingID,files:[...files]};setPendingFiles(pending);
  const okay=await run(async()=>{
   let next=draft;const blobs=new Map();
   for(const file of pending.files){const photo={id:id(),findingID,name:file.name,mime:file.type,size:file.size,sha256:await sha256(file)};if(!current())throw Object.assign(Error(),{code:'identity'});next=addPhoto(next,photo);blobs.set(photo.id,file);}
   await repository.save(updated(next,{}),blobs,draft.revision);
  });if(okay)setPendingFiles(null);
 }
 async function queue() {
  if(hasUnsaved){setError(l('Speichere oder verwerfe zuerst die Eingaben in den Formularen.','Save or discard the form input first.'));return;}
  if(!confirm(l('Diesen gespeicherten Entwurf für die Übertragung festschreiben? Danach bleiben Inhalt und Übertragungskennung unverändert.','Seal this saved draft for upload? Its content and operation identity then remain unchanged.')))return;
  await run(async()=>{await repository.save(sealBatch(draft,{operationID:id(),at:stamp()}),new Map(),draft.revision);});
 }
 async function acceptReceipt(receipt) {await repository.save(acknowledgeBatch(draft,receipt,scope),new Map(),draft.revision);if(current())await onAcknowledged();}
 async function publish() {await run(async()=>{const blobs=await repository.photos(draft.id);const receipt=await transport.publish(draft,blobs);if(!current())return;await acceptReceipt(receipt);});}
 async function checkOutcome() {await run(async()=>{const result=await transport.receipt(draft);if(result.exists)await acceptReceipt(result.receipt);else{const snapshot=await readCurrent();if(!current())return;setReview({snapshot,differences:diffBaseline(draft.baseline,snapshot),evidence:result});setConfirmed(false);}});}
 async function rebase() {
  if(!confirmed)return;
  await run(async()=>{const result=await transport.cancel(draft);if(result.exists){await acceptReceipt(result.receipt);return;}if(!current())return;await repository.rebase(draft.id,draft.revision,review.snapshot,result,true);setReview(null);setConfirmed(false);});
 }
 if(!current()||accessFailed)return <section className="workspacePage outbox"><button onClick={onClose}>{l('Schließen','Close')}</button><p role="alert">{l('Die aktuelle Anmeldung oder der Zugriff ist nicht mehr verfügbar.','The current account or access is unavailable.')}</p></section>;
 const condition=value=>({ok:l('In Ordnung','OK'),notice:l('Hinweis','Note'),defect:l('Mangel','Defect')}[value]);
 const changeLabel=path=>({title:l('Protokolltitel','Inspection title'),general_notes:l('Allgemeine Notizen','General notes'),tenant_name:l('Beteiligte Person','Participant'),tenant_email:l('E-Mail der beteiligten Person','Participant email'),inspection_at:l('Begehungstermin','Inspection date'),updated_at:l('Letzte Aktualisierung','Last update'),status:l('Protokollstatus','Inspection status'),completed_at:l('Abschlusszeit','Completion time'),property_id:l('Objektzuordnung','Property assignment'),unit_id:l('Einheitenzuordnung','Unit assignment'),rooms:l('Räume und Raumnotizen','Rooms and room notes'),findings:l('Feststellungen und Fotoanzahl','Findings and photo counts')}[path.split('.').at(-1)]??l('Weitere Protokollangaben','Other inspection information'));
 const showFact=(value,snapshot)=>{
  if(value===null)return <p>{l('Nicht hinterlegt','Not recorded')}</p>;
  if(Array.isArray(value))return value.length?<ul className="outboxFactList">{value.map((item,index)=><li key={item.id??index}><strong>{item.name??item.title??l('Eintrag','Entry')}</strong>{item.room_id&&<p>{snapshot.rooms.find(room=>room.id===item.room_id)?.name??l('Zugeordneter Raum','Assigned room')}</p>}{item.condition&&<p>{condition(item.condition)}</p>}{item.description&&<p>{item.description}</p>}{item.notes&&<p>{item.notes}</p>}{item.category&&<p>{item.category}</p>}{Number.isInteger(item.attachment_count)&&<p>{item.attachment_count} {l('Fotos','photos')}</p>}</li>)}</ul>:<p>{l('Keine Einträge','No entries')}</p>;
  if(typeof value==='string'&&/^\d{4}-\d\d-\d\dT/.test(value)&&Number.isFinite(Date.parse(value)))return <p>{new Date(value).toLocaleString(language)}</p>;
  if(value==='draft')return <p>{l('Entwurf','Draft')}</p>;if(value==='completed')return <p>{l('Abgeschlossen','Completed')}</p>;
  return <p>{String(value)}</p>;
 };

 return <section className="workspacePage outbox" aria-busy={busy}>
  <header className="outboxHeader"><button type="button" disabled={busy} onClick={close}>← {l('Zum Protokoll','Back to inspection')}</button><label>{l('Sprache','Language')}<select value={language} onChange={event=>setLanguage(event.target.value)}><option value="de">Deutsch</option><option value="en">English</option></select></label></header>
  <h1>{l('Lokaler Begehungs-Ausgang','Local inspection outbox')}</h1><h2>{initialSnapshot.protocol.title}</h2>
  <p>{l('Erfasse neue Räume, Feststellungen und Fotos lokal. Es wird erst durch deine ausdrückliche Übertragung etwas an das bestehende Protokoll gesendet.','Capture new rooms, findings and photos locally. Nothing is sent to the existing inspection until you explicitly publish it.')}</p>
  <p>{l('Nach dem Öffnen kannst du ohne Verbindung weiter erfassen. Zum erneuten Öffnen nach einem Neustart ist eine Online-Anmeldung mit Zugriff auf dieses Protokoll nötig. Lokale Daten sind kein Server-PDF und kein automatisch angelegter Mangel.','After opening, you can continue capturing without connectivity. Reopening after a restart requires online sign-in and access to this inspection. Local data is not a server PDF or an automatically created case.')}</p>
  {error&&<div role="alert" className="errorBox">{error}</div>}{busy&&<p role="status">{l('Bitte warten …','Please wait …')}</p>}
  {blocked?<><p>{l('Speichern bleibt gesperrt. Vorhandene Daten werden nicht ersetzt.','Saving stays blocked. Existing data is not replaced.')}</p><button disabled={busy} onClick={()=>run(async()=>{})}>{l('Erneut laden','Retry loading')}</button></>:<button type="button" disabled={busy||loading} onClick={newDraft}>{l('Neuen lokalen Entwurf speichern','Save a new local draft')}</button>}
  {loading&&<p>{l('Lokale Entwürfe werden geladen …','Loading local drafts …')}</p>}
  {!!drafts.length&&<label>{l('Gespeicherter Ausgang','Saved outbox')}<select disabled={busy} value={selectedID??''} onChange={event=>switchDraft(event.target.value)}>{drafts.map(value=><option key={value.id} value={value.id}>{new Date(value.createdAt).toLocaleString(language)} · {value.rooms.length}/{value.findings.length} · {value.state==='draft'?l('Lokal gespeichert','Saved locally'):value.state==='queued'?l('Wartet auf Bestätigung','Awaiting acknowledgement'):l('Vom Server bestätigt','Acknowledged by server')}</option>)}</select></label>}
  {draft&&<>
   <div className="outboxState" role="status"><strong>{draft.state==='draft'?l('Lokal gespeichert · noch nicht übertragen','Saved locally · not published'):draft.state==='queued'?l('Festgeschriebener Ausgang · noch nicht lokal bestätigt','Sealed outbox · not acknowledged locally'):l('Vom Server bestätigt','Acknowledged by server')}</strong><span>{draft.rooms.length} {l('neue Räume','new rooms')} · {draft.findings.length} {l('neue Feststellungen','new findings')} · {draft.photos.length} {l('Fotos','photos')}</span></div>
   {draft.state==='acknowledged'&&<div className="successBox"><p>{l('Diese Ergänzungen wurden durch eine passende Serverbestätigung übernommen. Öffne das bestehende Protokoll für PDF und die ausdrückliche Übernahme als Mangel.','A matching server receipt confirms these additions. Open the existing inspection for its PDF and explicit finding-to-case conversion.')}</p><button onClick={onClose}>{l('Bestehendes Protokoll öffnen','Open existing inspection')}</button></div>}
   {editable&&<div className="outboxForms"><form onSubmit={saveRoom}><h2>{roomEdit?l('Lokalen Raum bearbeiten','Edit local room'):l('Neuer lokaler Raum','New local room')}</h2><label>{l('Name','Name')}<input required maxLength={120} value={room.name} onChange={event=>setRoom({...room,name:event.target.value})}/></label><label>{l('Zustand','Condition')}<select value={room.condition} onChange={event=>setRoom({...room,condition:event.target.value})}>{['ok','notice','defect'].map(value=><option key={value} value={value}>{condition(value)}</option>)}</select></label><label>{l('Notiz','Note')}<textarea maxLength={1200} rows={3} value={room.notes} onChange={event=>setRoom({...room,notes:event.target.value})}/></label><button disabled={!valid(roomCandidate)}>{l('Raum lokal speichern','Save room locally')}</button>{roomEdit&&<button type="button" onClick={()=>{if(allowDiscard(roomDirty))clearRoom();}}>{l('Bearbeitung abbrechen','Cancel editing')}</button>}</form>
   <form onSubmit={saveFinding}><h2>{findingEdit?l('Lokale Feststellung bearbeiten','Edit local finding'):l('Neue lokale Feststellung','New local finding')}</h2><label>{l('Raum','Room')}<select value={finding.roomID} onChange={event=>setFinding({...finding,roomID:event.target.value})}><option value="">{l('Ohne Raum','No room')}</option>{[...draft.baseline.rooms,...draft.rooms].map(value=><option value={value.id} key={value.id}>{value.name}</option>)}</select></label><label>{l('Titel','Title')}<input required maxLength={180} value={finding.title} onChange={event=>setFinding({...finding,title:event.target.value})}/></label><label>{l('Beschreibung','Description')}<textarea required maxLength={3000} rows={4} value={finding.description} onChange={event=>setFinding({...finding,description:event.target.value})}/></label><label>{l('Kategorie','Category')}<input required maxLength={80} value={finding.category} onChange={event=>setFinding({...finding,category:event.target.value})}/></label><label>{l('Dringlichkeit','Urgency')}<select value={finding.severity} onChange={event=>setFinding({...finding,severity:event.target.value})}><option value="minor">{l('Gering','Minor')}</option><option value="normal">{l('Normal','Normal')}</option><option value="urgent">{l('Dringend','Urgent')}</option></select></label><button disabled={!valid(findingCandidate)}>{l('Feststellung lokal speichern','Save finding locally')}</button>{findingEdit&&<button type="button" onClick={()=>{if(allowDiscard(findingDirty))clearFinding();}}>{l('Bearbeitung abbrechen','Cancel editing')}</button>}</form></div>}
   {draft.rooms.map(value=><article className="outboxCard" key={value.id}><h3>{value.name}</h3><p>{condition(value.condition)}</p><p>{value.notes}</p>{editable&&<div className="outboxActions"><button onClick={()=>beginRoomEdit(value)}>{l('Bearbeiten','Edit')}</button><button disabled={draft.findings.some(item=>item.roomID===value.id)} onClick={()=>removeLocal({rooms:draft.rooms.filter(item=>item.id!==value.id)})}>{l('Lokalen Raum entfernen','Remove local room')}</button></div>}</article>)}
   {draft.findings.map(value=><article className="outboxCard" key={value.id}><h3>{value.title}</h3><p>{[...draft.baseline.rooms,...draft.rooms].find(item=>item.id===value.roomID)?.name??l('Ohne Raum','No room')} · {value.category} · {value.severity==='urgent'?l('Dringend','Urgent'):value.severity==='minor'?l('Gering','Minor'):l('Normal','Normal')}</p><p>{value.description}</p>{editable&&<div className="outboxActions"><button onClick={()=>beginFindingEdit(value)}>{l('Bearbeiten','Edit')}</button><button onClick={()=>removeLocal({findings:draft.findings.filter(item=>item.id!==value.id),photos:draft.photos.filter(item=>item.findingID!==value.id)})}>{l('Lokale Feststellung entfernen','Remove local finding')}</button></div>}
    <div className="outboxPhotos">{draft.photos.filter(photo=>photo.findingID===value.id).map(photo=><Photo key={photo.id} photo={photo} blob={gallery.get(photo.id)} editable={editable} l={l} onRemove={()=>removeLocal({photos:draft.photos.filter(item=>item.id!==photo.id)})}/>)}</div>
    {editable&&<label>{l('JPEG, PNG oder WebP lokal hinzufügen · höchstens 5 je Feststellung, 3 MB je Foto','Add JPEG, PNG or WebP locally · up to 5 per finding, 3 MB per photo')}<input type="file" accept="image/jpeg,image/png,image/webp" multiple disabled={busy} onChange={event=>{const files=[...event.target.files];if(files.length)void captureFiles(value.id,files);event.target.value='';}}/></label>}
   </article>)}
   {pendingFiles&&<div role="alert" className="outboxCard"><p>{l('Diese ausgewählten Fotos sind noch nicht gespeichert.','These selected photos have not been saved yet.')}</p><button disabled={busy} onClick={()=>captureFiles(pendingFiles.findingID,pendingFiles.files)}>{l('Dieselben Fotos erneut speichern','Retry saving these photos')}</button><button disabled={busy} onClick={()=>setPendingFiles(null)}>{l('Nicht gespeicherte Auswahl verwerfen','Discard unsaved selection')}</button></div>}
   {draft.state==='draft'&&<div className="outboxFooter"><button disabled={busy||blocked||(!draft.rooms.length&&!draft.findings.length)} onClick={queue}>{l('Gespeicherten Entwurf in den Ausgang legen','Seal saved draft for publishing')}</button></div>}
   {draft.state==='queued'&&<div className="outboxCard"><p>{l('Der Inhalt bleibt unverändert. Eine wiederholte Übertragung verwendet dieselbe Kennung. Eine unklare Übertragung wird nicht automatisch als fehlgeschlagen oder erfolgreich gewertet.','The content stays unchanged. Repeated uploads use the same operation identity. An unknown outcome is never automatically treated as failure or success.')}</p><div className="outboxActions"><button disabled={busy||blocked} onClick={publish}>{l('Ausgang übertragen / gleichen Versuch wiederholen','Publish outbox / retry same operation')}</button><button disabled={busy||blocked} onClick={checkOutcome}>{l('Bestätigung prüfen und Änderungen vergleichen','Check receipt and review changes')}</button></div></div>}
   {review&&draft.state==='queued'&&<div className="outboxCard"><h2>{l('Aktuellen Serverstand prüfen','Review current server record')}</h2><p>{review.differences.length?l('Der Serverstand hat sich geändert:','The server record has changed:'):l('Keine Inhaltsänderung gegenüber der gespeicherten Grundlage erkannt.','No content change detected against the saved baseline.')}</p>{review.differences.map((change,index)=><details key={index}><summary>{changeLabel(change.path)}</summary><h3>{l('Vorher','Before')}</h3>{showFact(change.before,draft.baseline)}<h3>{l('Aktuell','Current')}</h3>{showFact(change.after,review.snapshot)}</details>)}<p>{l('Eine reine fehlende Bestätigung entsperrt den Ausgang nicht. Nach deiner Bestätigung wird zuerst die alte Übertragungskennung auf dem Server gesperrt. Hat sie bereits übernommen, wird stattdessen die echte Bestätigung geladen.','A missing receipt alone never unlocks the outbox. After your confirmation, the old operation identity is first cancelled on the server. If already committed, its real receipt is loaded instead.')}</p><label className="outboxCheck"><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/>{l('Ich habe den aktuellen Stand geprüft und möchte die unveröffentlichten Ergänzungen auf dieser Grundlage weiter bearbeiten.','I reviewed the current record and want to continue editing unpublished additions against this baseline.')}</label><button disabled={busy||!confirmed||review.snapshot.protocol.status!=='draft'} onClick={rebase}>{l('Alte Übertragung sicher beenden und Entwurf weiter bearbeiten','Cancel old operation safely and continue editing')}</button><button disabled={busy} onClick={()=>setReview(null)}>{l('Ausgang unverändert lassen','Keep outbox unchanged')}</button></div>}
   {draft.state!=='queued'&&<button type="button" disabled={busy||blocked} onClick={()=>{if(confirm(l('Diesen lokalen Entwurf und seine lokalen Fotos löschen? Serverdaten bleiben bestehen.','Delete this local draft and its local photos? Server records are kept.')))void run(async()=>{await repository.remove(draft.id,draft.revision);resetForms();});}}>{l('Nur diesen lokalen Datensatz löschen','Delete only this local record')}</button>}
  </>}
 </section>;
}
