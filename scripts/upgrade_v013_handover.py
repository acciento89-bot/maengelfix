from pathlib import Path
import json,re
root=Path('.')
schema_p=root/'server/schema.sql'; server_p=root/'server/index.js'; app_p=root/'client/src/App.jsx'; css_p=root/'client/src/maengelfix-pro.css'; pkg_p=root/'server/package.json'
schema=schema_p.read_text(); server=server_p.read_text(); app=app_p.read_text(); css=css_p.read_text(); pkg=json.loads(pkg_p.read_text())

if '-- v0.13: Übergabe- und Abnahmeprotokolle' not in schema:
    schema += r'''

-- v0.13: Übergabe- und Abnahmeprotokolle mit Mängelübernahme
CREATE TABLE IF NOT EXISTS inspection_protocols (
  id text PRIMARY KEY,
  organization_id text REFERENCES organizations(id) ON DELETE CASCADE,
  property_id text REFERENCES properties(id) ON DELETE SET NULL,
  unit_id text REFERENCES units(id) ON DELETE SET NULL,
  created_by text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  protocol_type text NOT NULL DEFAULT 'handover',
  status text NOT NULL DEFAULT 'draft',
  title text NOT NULL,
  inspection_at timestamptz NOT NULL DEFAULT now(),
  tenant_name text,
  tenant_email text,
  general_notes text,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS inspection_protocols_org_idx ON inspection_protocols(organization_id,inspection_at DESC);
CREATE INDEX IF NOT EXISTS inspection_protocols_unit_idx ON inspection_protocols(unit_id,inspection_at DESC);

CREATE TABLE IF NOT EXISTS inspection_rooms (
  id text PRIMARY KEY,
  protocol_id text NOT NULL REFERENCES inspection_protocols(id) ON DELETE CASCADE,
  name text NOT NULL,
  position integer NOT NULL DEFAULT 0,
  condition text NOT NULL DEFAULT 'ok',
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS inspection_rooms_protocol_idx ON inspection_rooms(protocol_id,position);

CREATE TABLE IF NOT EXISTS inspection_findings (
  id text PRIMARY KEY,
  protocol_id text NOT NULL REFERENCES inspection_protocols(id) ON DELETE CASCADE,
  room_id text REFERENCES inspection_rooms(id) ON DELETE SET NULL,
  created_by text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title text NOT NULL,
  description text NOT NULL,
  category text NOT NULL DEFAULT 'Sonstiges',
  severity text NOT NULL DEFAULT 'normal',
  status text NOT NULL DEFAULT 'open',
  defect_case_id text REFERENCES defect_cases(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS inspection_findings_protocol_idx ON inspection_findings(protocol_id,status);

CREATE TABLE IF NOT EXISTS inspection_attachments (
  id text PRIMARY KEY,
  finding_id text NOT NULL REFERENCES inspection_findings(id) ON DELETE CASCADE,
  uploaded_by text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  original_name text NOT NULL,
  stored_name text NOT NULL,
  mime_type text NOT NULL,
  size_bytes integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS inspection_attachments_finding_idx ON inspection_attachments(finding_id,created_at);
'''
schema_p.write_text(schema)
pkg['version']='0.13.0'; pkg_p.write_text(json.dumps(pkg,ensure_ascii=False,indent=2)+'\n')
server=re.sub(r"res\.json\(\{ ok: true, service: 'maengelfix', version: '[^']+'[^}]*\}\);","res.json({ ok: true, service: 'maengelfix', version: '0.13.0', mail: smtpConfigured ? 'smtp' : 'manual' });",server,count=1)

anchor="app.get('/api/calendar', auth, async (req,res,next)=>{"
if "app.get('/api/inspections'" not in server:
    endpoints=r'''
async function inspectionAccess(userId, protocolId){
  const org=await organizationForUser(userId);
  const r=await pool.query(`SELECT ip.*,p.name property_name,p.street property_street,p.postal_code property_postal_code,p.city property_city,u.label unit_label,u.floor unit_floor
    FROM inspection_protocols ip LEFT JOIN properties p ON p.id=ip.property_id LEFT JOIN units u ON u.id=ip.unit_id
    WHERE ip.id=$1 AND ((ip.organization_id IS NOT NULL AND ip.organization_id=$2) OR (ip.organization_id IS NULL AND ip.created_by=$3))`,[protocolId,org?.id||null,userId]);
  return r.rows[0]||null;
}

app.get('/api/inspections',auth,async(req,res,next)=>{try{
 const org=await organizationForUser(req.user.id);let r;
 if(org) r=await pool.query(`SELECT ip.*,p.name property_name,u.label unit_label,(SELECT count(*)::int FROM inspection_findings f WHERE f.protocol_id=ip.id) finding_count,(SELECT count(*)::int FROM inspection_findings f WHERE f.protocol_id=ip.id AND f.status='open') open_finding_count FROM inspection_protocols ip LEFT JOIN properties p ON p.id=ip.property_id LEFT JOIN units u ON u.id=ip.unit_id WHERE ip.organization_id=$1 ORDER BY ip.inspection_at DESC`,[org.id]);
 else r=await pool.query(`SELECT ip.*,(SELECT count(*)::int FROM inspection_findings f WHERE f.protocol_id=ip.id) finding_count,(SELECT count(*)::int FROM inspection_findings f WHERE f.protocol_id=ip.id AND f.status='open') open_finding_count FROM inspection_protocols ip WHERE ip.organization_id IS NULL AND ip.created_by=$1 ORDER BY ip.inspection_at DESC`,[req.user.id]);
 res.json({protocols:r.rows,organization:org||null});
}catch(e){next(e)}});

app.post('/api/inspections',auth,async(req,res,next)=>{try{
 const org=await organizationForUser(req.user.id);const title=cleanText(req.body.title,180);if(!title)return res.status(400).json({error:'Bitte gib einen Titel an.'});
 const type=['handover','return','inspection'].includes(req.body.protocolType)?req.body.protocolType:'handover';let propertyId=cleanText(req.body.propertyId,80)||null,unitId=cleanText(req.body.unitId,80)||null;
 if(org){if(!propertyId||!unitId)return res.status(400).json({error:'Für Verwaltungsprotokolle sind Objekt und Einheit erforderlich.'});const u=await pool.query(`SELECT 1 FROM units u JOIN properties p ON p.id=u.property_id WHERE u.id=$1 AND p.id=$2 AND p.organization_id=$3`,[unitId,propertyId,org.id]);if(!u.rowCount)return res.status(400).json({error:'Objekt oder Einheit ist ungültig.'});}
 const pid=id();const r=await pool.query(`INSERT INTO inspection_protocols (id,organization_id,property_id,unit_id,created_by,protocol_type,title,inspection_at,tenant_name,tenant_email,general_notes) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING *`,[pid,org?.id||null,propertyId,unitId,req.user.id,type,title,req.body.inspectionAt||new Date(),cleanText(req.body.tenantName,160),cleanText(req.body.tenantEmail,254)?.toLowerCase(),cleanText(req.body.generalNotes,3000)]);
 if(org)await writeAudit({organizationId:org.id,userId:req.user.id,action:'inspection_created',entityType:'inspection_protocol',entityId:pid,summary:`Protokoll „${title}“ angelegt.`});res.status(201).json({protocol:r.rows[0]});
}catch(e){next(e)}});

app.get('/api/inspections/:protocolId',auth,async(req,res,next)=>{try{
 const p=await inspectionAccess(req.user.id,req.params.protocolId);if(!p)return res.status(404).json({error:'Protokoll nicht gefunden.'});
 const [rooms,findings]=await Promise.all([pool.query(`SELECT * FROM inspection_rooms WHERE protocol_id=$1 ORDER BY position,name`,[p.id]),pool.query(`SELECT f.*,r.name room_name,(SELECT count(*)::int FROM inspection_attachments a WHERE a.finding_id=f.id) attachment_count FROM inspection_findings f LEFT JOIN inspection_rooms r ON r.id=f.room_id WHERE f.protocol_id=$1 ORDER BY r.position,f.created_at`,[p.id])]);
 res.json({protocol:p,rooms:rooms.rows,findings:findings.rows});
}catch(e){next(e)}});

app.post('/api/inspections/:protocolId/rooms',auth,async(req,res,next)=>{try{const p=await inspectionAccess(req.user.id,req.params.protocolId);if(!p)return res.status(404).json({error:'Protokoll nicht gefunden.'});if(p.status==='completed')return res.status(409).json({error:'Abgeschlossene Protokolle können nicht mehr verändert werden.'});const name=cleanText(req.body.name,120);if(!name)return res.status(400).json({error:'Raumname fehlt.'});const pos=(await pool.query('SELECT count(*)::int n FROM inspection_rooms WHERE protocol_id=$1',[p.id])).rows[0].n;const r=await pool.query(`INSERT INTO inspection_rooms (id,protocol_id,name,position,condition,notes) VALUES ($1,$2,$3,$4,$5,$6) RETURNING *`,[id(),p.id,name,pos,['ok','notice','defect'].includes(req.body.condition)?req.body.condition:'ok',cleanText(req.body.notes,1200)]);res.status(201).json({room:r.rows[0]})}catch(e){next(e)}});

app.patch('/api/inspection-rooms/:roomId',auth,async(req,res,next)=>{try{const rr=await pool.query('SELECT protocol_id FROM inspection_rooms WHERE id=$1',[req.params.roomId]);if(!rr.rowCount)return res.status(404).json({error:'Raum nicht gefunden.'});const p=await inspectionAccess(req.user.id,rr.rows[0].protocol_id);if(!p)return res.status(403).json({error:'Kein Zugriff.'});const r=await pool.query(`UPDATE inspection_rooms SET name=COALESCE($2,name),condition=$3,notes=$4 WHERE id=$1 RETURNING *`,[req.params.roomId,cleanText(req.body.name,120),['ok','notice','defect'].includes(req.body.condition)?req.body.condition:'ok',cleanText(req.body.notes,1200)]);res.json({room:r.rows[0]})}catch(e){next(e)}});

app.post('/api/inspections/:protocolId/findings',auth,async(req,res,next)=>{try{const p=await inspectionAccess(req.user.id,req.params.protocolId);if(!p)return res.status(404).json({error:'Protokoll nicht gefunden.'});if(p.status==='completed')return res.status(409).json({error:'Abgeschlossene Protokolle können nicht mehr verändert werden.'});const title=cleanText(req.body.title,180),description=cleanText(req.body.description,3000);if(!title||!description)return res.status(400).json({error:'Titel und Beschreibung sind erforderlich.'});const roomId=cleanText(req.body.roomId,80)||null;if(roomId){const room=await pool.query('SELECT 1 FROM inspection_rooms WHERE id=$1 AND protocol_id=$2',[roomId,p.id]);if(!room.rowCount)return res.status(400).json({error:'Raum gehört nicht zum Protokoll.'});}const fid=id();const r=await pool.query(`INSERT INTO inspection_findings (id,protocol_id,room_id,created_by,title,description,category,severity) VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *`,[fid,p.id,roomId,req.user.id,title,description,cleanText(req.body.category,80)||'Sonstiges',['minor','normal','urgent'].includes(req.body.severity)?req.body.severity:'normal']);if(p.organization_id)await writeAudit({organizationId:p.organization_id,userId:req.user.id,action:'inspection_finding_created',entityType:'inspection_finding',entityId:fid,summary:`Feststellung „${title}“ im Protokoll ergänzt.`});res.status(201).json({finding:r.rows[0]})}catch(e){next(e)}});

app.post('/api/inspection-findings/:findingId/attachments',auth,upload.array('images',5),async(req,res,next)=>{try{const fr=await pool.query('SELECT protocol_id FROM inspection_findings WHERE id=$1',[req.params.findingId]);if(!fr.rowCount)return res.status(404).json({error:'Feststellung nicht gefunden.'});const p=await inspectionAccess(req.user.id,fr.rows[0].protocol_id);if(!p)return res.status(403).json({error:'Kein Zugriff.'});const out=[];for(const file of req.files||[]){const aid=id();const r=await pool.query(`INSERT INTO inspection_attachments (id,finding_id,uploaded_by,original_name,stored_name,mime_type,size_bytes) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id,original_name,mime_type,size_bytes,created_at`,[aid,req.params.findingId,req.user.id,cleanText(file.originalname,250),file.filename,file.mimetype,file.size]);out.push(r.rows[0])}res.status(201).json({attachments:out})}catch(e){next(e)}});

app.get('/api/inspection-attachments/:attachmentId',auth,async(req,res,next)=>{try{const r=await pool.query(`SELECT a.*,f.protocol_id FROM inspection_attachments a JOIN inspection_findings f ON f.id=a.finding_id WHERE a.id=$1`,[req.params.attachmentId]);if(!r.rowCount)return res.status(404).end();const p=await inspectionAccess(req.user.id,r.rows[0].protocol_id);if(!p)return res.status(403).end();res.type(r.rows[0].mime_type).sendFile(path.join(uploadDir,r.rows[0].stored_name))}catch(e){next(e)}});

app.post('/api/inspection-findings/:findingId/create-case',auth,async(req,res,next)=>{const client=await pool.connect();try{
 const fr=await client.query(`SELECT f.*,r.name room_name,ip.organization_id,ip.property_id,ip.unit_id,ip.title protocol_title,p.name property_name,u.label unit_label FROM inspection_findings f JOIN inspection_protocols ip ON ip.id=f.protocol_id LEFT JOIN inspection_rooms r ON r.id=f.room_id LEFT JOIN properties p ON p.id=ip.property_id LEFT JOIN units u ON u.id=ip.unit_id WHERE f.id=$1`,[req.params.findingId]);if(!fr.rowCount)return res.status(404).json({error:'Feststellung nicht gefunden.'});const f=fr.rows[0];const p=await inspectionAccess(req.user.id,f.protocol_id);if(!p)return res.status(403).json({error:'Kein Zugriff.'});if(f.defect_case_id)return res.status(409).json({error:'Für diese Feststellung wurde bereits ein Mangel angelegt.',caseId:f.defect_case_id});
 const cid=id();await client.query('BEGIN');await client.query(`INSERT INTO defect_cases (id,user_id,organization_id,property_id,unit_id,title,category,description,property_label,location_label,discovered_on,status) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)`,[cid,req.user.id,f.organization_id,f.property_id,f.unit_id,f.title,f.category,f.description,f.property_name,f.room_name||f.unit_label,new Date().toISOString().slice(0,10),f.organization_id?'received':'draft']);
 await client.query(`INSERT INTO case_events (id,case_id,user_id,event_type,note,visibility) VALUES ($1,$2,$3,'created',$4,'shared')`,[id(),cid,req.user.id,`Mangel aus ${f.protocol_title} übernommen.`]);
 const photos=await client.query('SELECT * FROM inspection_attachments WHERE finding_id=$1',[f.id]);for(const a of photos.rows)await client.query(`INSERT INTO attachments (id,case_id,user_id,original_name,stored_name,mime_type,size_bytes) VALUES ($1,$2,$3,$4,$5,$6,$7)`,[id(),cid,req.user.id,a.original_name,a.stored_name,a.mime_type,a.size_bytes]);
 await client.query(`UPDATE inspection_findings SET defect_case_id=$2,status='converted',updated_at=now() WHERE id=$1`,[f.id,cid]);if(f.organization_id)await writeAudit({organizationId:f.organization_id,userId:req.user.id,caseId:cid,action:'inspection_finding_converted',entityType:'inspection_finding',entityId:f.id,summary:`Feststellung „${f.title}“ als Mangel übernommen.`});await client.query('COMMIT');res.status(201).json({caseId:cid});
}catch(e){await client.query('ROLLBACK');next(e)}finally{client.release()}});

app.post('/api/inspections/:protocolId/complete',auth,async(req,res,next)=>{try{const p=await inspectionAccess(req.user.id,req.params.protocolId);if(!p)return res.status(404).json({error:'Protokoll nicht gefunden.'});const r=await pool.query(`UPDATE inspection_protocols SET status='completed',completed_at=now(),updated_at=now() WHERE id=$1 RETURNING *`,[p.id]);if(p.organization_id)await writeAudit({organizationId:p.organization_id,userId:req.user.id,action:'inspection_completed',entityType:'inspection_protocol',entityId:p.id,summary:`Protokoll „${p.title}“ abgeschlossen.`});res.json({protocol:r.rows[0]})}catch(e){next(e)}});

app.get('/api/inspections/:protocolId/pdf',auth,async(req,res,next)=>{try{const p=await inspectionAccess(req.user.id,req.params.protocolId);if(!p)return res.status(404).end();const [rooms,findings]=await Promise.all([pool.query('SELECT * FROM inspection_rooms WHERE protocol_id=$1 ORDER BY position',[p.id]),pool.query(`SELECT f.*,r.name room_name FROM inspection_findings f LEFT JOIN inspection_rooms r ON r.id=f.room_id WHERE f.protocol_id=$1 ORDER BY r.position,f.created_at`,[p.id])]);const doc=new PDFDocument({size:'A4',margins:{top:44,right:48,bottom:48,left:48}});res.type('application/pdf');res.setHeader('Content-Disposition',`inline; filename="maengelfix-protokoll-${p.id.split('-')[0]}.pdf"`);doc.pipe(res);doc.rect(0,0,doc.page.width,86).fill('#18212B');doc.fillColor('#fff').font('Helvetica-Bold').fontSize(21).text('MängelFix',48,24);doc.font('Helvetica').fontSize(9).fillColor('#bdc5cc').text(p.protocol_type==='return'?'ABNAHMEPROTOKOLL':'ÜBERGABEPROTOKOLL',48,54,{characterSpacing:1.2});doc.fillColor('#18212B').font('Helvetica-Bold').fontSize(18).text(p.title,48,112);doc.font('Helvetica').fontSize(9).fillColor('#66717d').text(`${new Date(p.inspection_at).toLocaleString('de-DE')} · ${[p.property_name,p.unit_label].filter(Boolean).join(' · ')}`,48,142);let y=180;for(const room of rooms.rows){if(y>700){doc.addPage();y=60}doc.roundedRect(48,y,499,34,4).fill('#f2f4f5');doc.fillColor('#18212B').font('Helvetica-Bold').fontSize(11).text(room.name,60,y+10);doc.fontSize(8).fillColor(room.condition==='defect'?'#b42318':'#66717d').text(room.condition==='defect'?'MANGEL':room.condition==='notice'?'HINWEIS':'OK',450,y+11,{width:80,align:'right'});y+=44;const rf=findings.rows.filter(f=>f.room_id===room.id);for(const f of rf){doc.fillColor('#18212B').font('Helvetica-Bold').fontSize(10).text(`• ${f.title}`,62,y,{width:470});y=doc.y+3;doc.font('Helvetica').fontSize(8.5).fillColor('#59646e').text(f.description,74,y,{width:455});y=doc.y+10}if(room.notes){doc.font('Helvetica-Oblique').fontSize(8).fillColor('#6f7a86').text(room.notes,62,y,{width:470});y=doc.y+10}}const loose=findings.rows.filter(f=>!f.room_id);if(loose.length){doc.fillColor('#18212B').font('Helvetica-Bold').fontSize(11).text('Weitere Feststellungen',48,y+8);y=doc.y+8;for(const f of loose){doc.fontSize(9).text(`• ${f.title}: ${f.description}`,62,y,{width:470});y=doc.y+8}}doc.font('Helvetica').fontSize(8).fillColor('#7a8490').text(`Feststellungen: ${findings.rowCount} · als Mangel übernommen: ${findings.rows.filter(f=>f.defect_case_id).length}`,48,doc.page.height-60,{width:499,align:'center'});doc.end()}catch(e){next(e)}});
'''
    server=server.replace(anchor,endpoints+anchor)
server_p.write_text(server)

# Client
component_anchor="const calendarTypeLabels="
if 'function InspectionsView(' not in app:
    components=r'''
const inspectionTypeLabels={handover:'Übergabe',return:'Abnahme / Rückgabe',inspection:'Mängelprüfung'};
const roomConditionLabels={ok:'In Ordnung',notice:'Hinweis',defect:'Mangel'};
function InspectionsView({onSelectCase}){
 const [data,setData]=useState({protocols:[],organization:null});const [detail,setDetail]=useState(null);const [show,setShow]=useState(false);const [error,setError]=useState('');const [properties,setProperties]=useState([]);const [units,setUnits]=useState([]);const [form,setForm]=useState({title:'Wohnungsübergabe',protocolType:'handover',inspectionAt:'',propertyId:'',unitId:'',tenantName:'',tenantEmail:'',generalNotes:''});
 async function load(){try{setData(await api('/api/inspections'))}catch(e){setError(e.message)}}useEffect(()=>{load()},[]);useEffect(()=>{if(data.organization)api('/api/properties').then(x=>setProperties(x.properties||[])).catch(()=>{})},[data.organization]);async function chooseProperty(id){setForm({...form,propertyId:id,unitId:''});if(id)try{setUnits((await api(`/api/properties/${id}`)).units||[])}catch(e){setError(e.message)}}async function create(e){e.preventDefault();try{const r=await api('/api/inspections',{method:'POST',body:JSON.stringify(form)});setShow(false);await load();setDetail(r.protocol.id)}catch(e){setError(e.message)}}
 if(detail)return <InspectionDetail protocolId={detail} onBack={()=>{setDetail(null);load()}} onSelectCase={onSelectCase}/>;
 return <div className="workspacePage inspectionsPage"><div className="workspaceHeading"><div><span>ÜBERGABE & ABNAHME</span><h1>Mängelprotokolle</h1><p>Raum für Raum prüfen, Feststellungen fotografieren und echte Mängel direkt übernehmen.</p></div><button className="workspacePrimary" onClick={()=>setShow(true)}>+ Neues Protokoll</button></div>{error&&<div className="errorBox">{error}</div>}<div className="inspectionGrid">{data.protocols.length?data.protocols.map(p=><button className="inspectionCard" key={p.id} onClick={()=>setDetail(p.id)}><span>{inspectionTypeLabels[p.protocol_type]||p.protocol_type}</span><h2>{p.title}</h2><p>{[p.property_name,p.unit_label].filter(Boolean).join(' · ')||'Privates Protokoll'}</p><div><b>{p.finding_count||0} Feststellungen</b><strong>{p.open_finding_count||0} offen</strong></div><small>{fmtDate(p.inspection_at)} · {p.status==='completed'?'Abgeschlossen':'Entwurf'}</small></button>):<div className="emptyCard workspaceEmpty">Noch kein Übergabe- oder Abnahmeprotokoll vorhanden.</div>}</div>{show&&<div className="modalBackdrop" onMouseDown={()=>setShow(false)}><div className="modal proModal" onMouseDown={e=>e.stopPropagation()}><div className="modalHeader"><div><div className="eyebrow">MÄNGELPROTOKOLL</div><h2>Neues Protokoll</h2></div><button className="iconButton" onClick={()=>setShow(false)}>×</button></div><form className="caseForm" onSubmit={create}><label>Art<select value={form.protocolType} onChange={e=>setForm({...form,protocolType:e.target.value})}><option value="handover">Übergabe</option><option value="return">Abnahme / Rückgabe</option><option value="inspection">Mängelprüfung</option></select></label><label>Titel<input required value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label>{data.organization&&<><label>Objekt<select required value={form.propertyId} onChange={e=>chooseProperty(e.target.value)}><option value="">Objekt wählen…</option>{properties.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label>Einheit<select required value={form.unitId} onChange={e=>setForm({...form,unitId:e.target.value})}><option value="">Einheit wählen…</option>{units.map(u=><option key={u.id} value={u.id}>{u.label}</option>)}</select></label></>}<div className="formGrid two"><label>Termin<input type="datetime-local" value={form.inspectionAt} onChange={e=>setForm({...form,inspectionAt:e.target.value})}/></label><label>Mieter / Beteiligter<input value={form.tenantName} onChange={e=>setForm({...form,tenantName:e.target.value})}/></label></div><label>Allgemeine Notiz<textarea rows="3" value={form.generalNotes} onChange={e=>setForm({...form,generalNotes:e.target.value})}/></label><button className="primaryButton">Protokoll starten</button></form></div></div>}</div>;
}

function InspectionDetail({protocolId,onBack,onSelectCase}){
 const [data,setData]=useState(null);const [error,setError]=useState('');const [room,setRoom]=useState({name:'',condition:'ok',notes:''});const [finding,setFinding]=useState({roomId:'',title:'',description:'',category:'Sonstiges',severity:'normal'});async function load(){try{setData(await api(`/api/inspections/${protocolId}`))}catch(e){setError(e.message)}}useEffect(()=>{load()},[protocolId]);async function addRoom(e){e.preventDefault();try{await api(`/api/inspections/${protocolId}/rooms`,{method:'POST',body:JSON.stringify(room)});setRoom({name:'',condition:'ok',notes:''});await load()}catch(e){setError(e.message)}}async function addFinding(e){e.preventDefault();try{await api(`/api/inspections/${protocolId}/findings`,{method:'POST',body:JSON.stringify(finding)});setFinding({...finding,title:'',description:''});await load()}catch(e){setError(e.message)}}async function convert(f){try{const r=await api(`/api/inspection-findings/${f.id}/create-case`,{method:'POST'});await load();onSelectCase(r.caseId)}catch(e){setError(e.message)}}async function upload(f,files){const fd=new FormData();[...files].forEach(x=>fd.append('images',x));try{await api(`/api/inspection-findings/${f.id}/attachments`,{method:'POST',body:fd});await load()}catch(e){setError(e.message)}}async function complete(){if(!confirm('Protokoll abschließen? Danach sollten keine weiteren Feststellungen mehr ergänzt werden.'))return;try{await api(`/api/inspections/${protocolId}/complete`,{method:'POST'});await load()}catch(e){setError(e.message)}}if(!data)return <div className="workspacePage"><div className="emptyCard">Protokoll wird geladen…</div></div>;const p=data.protocol,locked=p.status==='completed';return <div className="workspacePage inspectionDetail"><div className="detailTop"><button className="backButton" onClick={onBack}>← Protokolle</button><div className="detailActions"><a className="secondaryButton linkButton" href={`/api/inspections/${p.id}/pdf`} target="_blank" rel="noreferrer">PDF öffnen</a>{!locked&&<button className="primaryButton" onClick={complete}>Protokoll abschließen</button>}</div></div><div className="workspaceHeading"><div><span>{inspectionTypeLabels[p.protocol_type]}</span><h1>{p.title}</h1><p>{[p.property_name,p.unit_label,p.tenant_name].filter(Boolean).join(' · ')}</p></div></div>{error&&<div className="errorBox">{error}</div>}<div className="inspectionSummary"><article><span>RÄUME</span><b>{data.rooms.length}</b></article><article><span>FESTSTELLUNGEN</span><b>{data.findings.length}</b></article><article><span>ALS MANGEL</span><b>{data.findings.filter(f=>f.defect_case_id).length}</b></article></div>{!locked&&<div className="inspectionForms"><form className="workspacePanel" onSubmit={addRoom}><h2>Raum hinzufügen</h2><label>Raum<input required value={room.name} onChange={e=>setRoom({...room,name:e.target.value})} placeholder="z. B. Badezimmer"/></label><label>Zustand<select value={room.condition} onChange={e=>setRoom({...room,condition:e.target.value})}>{Object.entries(roomConditionLabels).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label><label>Notiz<textarea rows="2" value={room.notes} onChange={e=>setRoom({...room,notes:e.target.value})}/></label><button className="primaryButton">Raum übernehmen</button></form><form className="workspacePanel" onSubmit={addFinding}><h2>Feststellung / Mangel</h2><label>Raum<select value={finding.roomId} onChange={e=>setFinding({...finding,roomId:e.target.value})}><option value="">Ohne Raum</option>{data.rooms.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label><label>Titel<input required value={finding.title} onChange={e=>setFinding({...finding,title:e.target.value})}/></label><label>Beschreibung<textarea required rows="3" value={finding.description} onChange={e=>setFinding({...finding,description:e.target.value})}/></label><div className="formGrid two"><label>Kategorie<select value={finding.category} onChange={e=>setFinding({...finding,category:e.target.value})}>{categories.map(c=><option key={c}>{c}</option>)}</select></label><label>Dringlichkeit<select value={finding.severity} onChange={e=>setFinding({...finding,severity:e.target.value})}><option value="minor">Gering</option><option value="normal">Normal</option><option value="urgent">Dringend</option></select></label></div><button className="primaryButton">Feststellung hinzufügen</button></form></div>}<div className="inspectionRooms">{data.rooms.map(r=><section className={`workspacePanel inspectionRoom condition-${r.condition}`} key={r.id}><div className="inspectionRoomHead"><div><span>{roomConditionLabels[r.condition]}</span><h2>{r.name}</h2>{r.notes&&<p>{r.notes}</p>}</div><b>{data.findings.filter(f=>f.room_id===r.id).length}</b></div><div className="findingList">{data.findings.filter(f=>f.room_id===r.id).map(f=><article className="findingRow" key={f.id}><div><span>{f.category} · {f.severity==='urgent'?'Dringend':f.severity==='minor'?'Gering':'Normal'}</span><h3>{f.title}</h3><p>{f.description}</p><small>{f.attachment_count} Foto{f.attachment_count===1?'':'s'}</small></div><div>{!locked&&<label className="secondaryButton uploadButton">+ Fotos<input type="file" accept="image/*" multiple onChange={e=>upload(f,e.target.files)}/></label>}{f.defect_case_id?<button className="secondaryButton" onClick={()=>onSelectCase(f.defect_case_id)}>Mangel öffnen →</button>:<button className="primaryButton" onClick={()=>convert(f)}>Als Mangel übernehmen</button>}</div></article>)}</div></section>)}{data.findings.filter(f=>!f.room_id).length>0&&<section className="workspacePanel inspectionRoom"><h2>Weitere Feststellungen</h2><div className="findingList">{data.findings.filter(f=>!f.room_id).map(f=><article className="findingRow" key={f.id}><div><h3>{f.title}</h3><p>{f.description}</p></div><div>{f.defect_case_id?<button className="secondaryButton" onClick={()=>onSelectCase(f.defect_case_id)}>Mangel öffnen →</button>:<button className="primaryButton" onClick={()=>convert(f)}>Als Mangel übernehmen</button>}</div></article>)}</div></section>}</div></div>;
}

'''
    app=app.replace(component_anchor,components+component_anchor)
app=app.replace("else if (view === 'calendar') content = <CalendarView onSelect={setSelected} />;","else if (view === 'inspections') content = <InspectionsView onSelectCase={setSelected} />;\n  else if (view === 'calendar') content = <CalendarView onSelect={setSelected} />;")
cal_btn="<button className={view === 'calendar' ? 'active' : ''} onClick={() => { setSelected(null); setView('calendar'); }}><span>K</span>Kalender</button>"
if cal_btn in app and "setView('inspections')" not in app:
    app=app.replace(cal_btn,"<button className={view === 'inspections' ? 'active' : ''} onClick={() => { setSelected(null); setView('inspections'); }}><span>Ü</span>Übergabe / Abnahme</button>"+cal_btn)
app_p.write_text(app)

css += r'''
/* v0.13 Übergabe-/Abnahmeprotokolle */
.inspectionGrid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.inspectionCard{border:1px solid #dce2e5;background:#fff;border-radius:13px;padding:20px;text-align:left}.inspectionCard>span,.inspectionRoomHead span{font-size:10px;font-weight:800;letter-spacing:.1em;color:#66717d}.inspectionCard h2{margin:7px 0}.inspectionCard p{color:#6d7881;min-height:34px}.inspectionCard>div{display:flex;justify-content:space-between;border-top:1px solid #e6eaec;padding-top:12px;margin-top:14px}.inspectionCard strong{color:#b42318}.inspectionCard small{display:block;margin-top:12px;color:#7a8490}.inspectionSummary{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:16px 0}.inspectionSummary article{background:#18212b;color:#fff;border-radius:11px;padding:18px}.inspectionSummary span{display:block;font-size:10px;letter-spacing:.1em;color:#adb6bf}.inspectionSummary b{font-size:27px}.inspectionForms{display:grid;grid-template-columns:1fr 1.35fr;gap:16px;margin:18px 0}.inspectionForms form{display:grid;gap:11px}.inspectionForms label{display:grid;gap:6px;font-weight:700;font-size:13px}.inspectionRooms{display:grid;gap:14px}.inspectionRoom{border-left:5px solid #7d8992}.inspectionRoom.condition-defect{border-left-color:#b42318}.inspectionRoom.condition-notice{border-left-color:#d98b22}.inspectionRoomHead{display:flex;justify-content:space-between;gap:20px}.inspectionRoomHead h2{margin:5px 0}.inspectionRoomHead>b{font-size:24px}.findingList{display:grid;gap:9px;margin-top:14px}.findingRow{display:flex;justify-content:space-between;gap:20px;padding:14px;border:1px solid #e0e5e7;border-radius:9px}.findingRow h3{margin:4px 0}.findingRow p{margin:0;color:#59656f}.findingRow span,.findingRow small{font-size:11px;color:#78838c}.findingRow>div:last-child{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.detailActions{display:flex;gap:8px}@media(max-width:900px){.inspectionGrid{grid-template-columns:1fr 1fr}.inspectionForms{grid-template-columns:1fr}}@media(max-width:620px){.inspectionGrid,.inspectionSummary{grid-template-columns:1fr}.findingRow{flex-direction:column}.detailTop{align-items:flex-start}.detailActions{flex-wrap:wrap}}
'''
css_p.write_text(css)
print('v0.13 handover protocol upgrade prepared')
