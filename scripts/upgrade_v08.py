from pathlib import Path
import json

root = Path('.')
schema_path = root/'server/schema.sql'
server_path = root/'server/index.js'
app_path = root/'client/src/App.jsx'
css_path = root/'client/src/maengelfix-pro.css'
pkg_path = root/'server/package.json'

schema = schema_path.read_text()
server = server_path.read_text()
app = app_path.read_text()
css = css_path.read_text()
pkg = json.loads(pkg_path.read_text())

schema_block = r'''

-- v0.8: Dienstleister & Arbeitsaufträge
CREATE TABLE IF NOT EXISTS service_providers (
  id text PRIMARY KEY,
  organization_id text NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  company_name text NOT NULL,
  trade text NOT NULL DEFAULT 'Sonstiges',
  contact_name text,
  email text,
  phone text,
  street text,
  postal_code text,
  city text,
  notes text,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS service_providers_org_idx ON service_providers(organization_id, active, company_name);

CREATE TABLE IF NOT EXISTS work_orders (
  id text PRIMARY KEY,
  organization_id text NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  case_id text NOT NULL REFERENCES defect_cases(id) ON DELETE CASCADE,
  provider_id text NOT NULL REFERENCES service_providers(id) ON DELETE RESTRICT,
  created_by text NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  title text NOT NULL,
  description text NOT NULL,
  status text NOT NULL DEFAULT 'draft',
  due_on date,
  scheduled_for timestamptz,
  contractor_note text,
  token_hash text NOT NULL UNIQUE,
  token_expires_at timestamptz NOT NULL,
  sent_at timestamptz,
  accepted_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS work_orders_org_idx ON work_orders(organization_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS work_orders_case_idx ON work_orders(case_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS work_orders_provider_idx ON work_orders(provider_id, updated_at DESC);
'''
if '-- v0.8: Dienstleister & Arbeitsaufträge' not in schema:
    schema += schema_block
schema_path.write_text(schema)

pkg['version'] = '0.8.0'
pkg_path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + '\n')

server = server.replace("res.json({ ok: true, service: 'maengelfix', version: '0.7.0' });", "res.json({ ok: true, service: 'maengelfix', version: '0.8.0' });")

anchor = "app.get('/api/management/overview', auth, async (req, res, next) => {"
server_block = r'''

const workOrderStatuses = new Set(['draft','sent','accepted','scheduled','completed','declined']);

function contractorUrl(token) {
  return `${appOrigin}/auftrag/${token}`;
}

async function providerForOrganization(providerId, organizationId) {
  const result = await pool.query('SELECT * FROM service_providers WHERE id=$1 AND organization_id=$2 AND active=true', [providerId, organizationId]);
  return result.rows[0] || null;
}

async function sendWorkOrderMail({ provider, organization, item, portalUrl }) {
  if (!mailer || !provider.email) return false;
  const safeTitle = String(item.title || 'Arbeitsauftrag');
  await mailer.sendMail({
    from: process.env.SMTP_FROM || 'MängelFix <noreply@kamilunavo.com>',
    to: provider.email,
    subject: `Arbeitsauftrag von ${organization.name}: ${safeTitle}`,
    text: `${organization.name} hat Ihnen einen Arbeitsauftrag über MängelFix gesendet.\n\n${safeTitle}\n${item.description}\n\nAuftrag öffnen: ${portalUrl}\n\nDer Link ist 30 Tage gültig.`,
    html: `<div style="font-family:Arial,sans-serif;max-width:640px;margin:auto;color:#18212b"><h2 style="margin-bottom:4px">MängelFix</h2><p style="color:#66717d;margin-top:0">Digitaler Arbeitsauftrag</p><p><b>${organization.name}</b> hat Ihnen einen Arbeitsauftrag gesendet.</p><div style="background:#f4f6f8;padding:18px;border-radius:8px;margin:20px 0"><h3 style="margin-top:0">${safeTitle}</h3><p style="white-space:pre-wrap">${String(item.description || '')}</p></div><p><a href="${portalUrl}" style="background:#2457d6;color:#fff;text-decoration:none;padding:12px 18px;border-radius:6px;display:inline-block">Arbeitsauftrag öffnen</a></p><p style="font-size:12px;color:#7a8490">Der persönliche Link ist 30 Tage gültig und darf nur an die zuständige Person weitergegeben werden.</p></div>`
  });
  return true;
}

app.get('/api/providers', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization) return res.status(403).json({error:'Dienstleister sind im Hausverwaltungs-Arbeitsbereich verfügbar.'});
    const result=await pool.query(`SELECT sp.*,
      (SELECT count(*)::int FROM work_orders wo WHERE wo.provider_id=sp.id) AS order_count,
      (SELECT count(*)::int FROM work_orders wo WHERE wo.provider_id=sp.id AND wo.status NOT IN ('completed','declined')) AS open_order_count
      FROM service_providers sp WHERE sp.organization_id=$1 AND sp.active=true ORDER BY sp.company_name`,[organization.id]);
    res.json({providers:result.rows});
  } catch(error){next(error);}
});

app.post('/api/providers', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization || !['owner','admin'].includes(organization.role)) return res.status(403).json({error:'Nur Inhaber und Admins können Dienstleister anlegen.'});
    const companyName=cleanText(req.body.companyName,180); const trade=cleanText(req.body.trade,100)||'Sonstiges';
    if(!companyName) return res.status(400).json({error:'Bitte gib den Firmennamen an.'});
    const result=await pool.query(`INSERT INTO service_providers (id,organization_id,company_name,trade,contact_name,email,phone,street,postal_code,city,notes)
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING *`,[id(),organization.id,companyName,trade,cleanText(req.body.contactName,160),cleanText(req.body.email,254)?.toLowerCase(),cleanText(req.body.phone,60),cleanText(req.body.street,180),cleanText(req.body.postalCode,20),cleanText(req.body.city,120),cleanText(req.body.notes,2000)]);
    res.status(201).json({provider:result.rows[0]});
  } catch(error){next(error);}
});

app.patch('/api/providers/:providerId', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization || !['owner','admin'].includes(organization.role)) return res.status(403).json({error:'Nur Inhaber und Admins können Dienstleister bearbeiten.'});
    const current=await pool.query('SELECT * FROM service_providers WHERE id=$1 AND organization_id=$2',[req.params.providerId,organization.id]);
    if(!current.rowCount) return res.status(404).json({error:'Dienstleister nicht gefunden.'});
    const old=current.rows[0];
    const result=await pool.query(`UPDATE service_providers SET company_name=$3,trade=$4,contact_name=$5,email=$6,phone=$7,street=$8,postal_code=$9,city=$10,notes=$11,active=$12,updated_at=now() WHERE id=$1 AND organization_id=$2 RETURNING *`,[req.params.providerId,organization.id,cleanText(req.body.companyName??old.company_name,180),cleanText(req.body.trade??old.trade,100)||'Sonstiges',cleanText(req.body.contactName??old.contact_name,160),cleanText(req.body.email??old.email,254)?.toLowerCase(),cleanText(req.body.phone??old.phone,60),cleanText(req.body.street??old.street,180),cleanText(req.body.postalCode??old.postal_code,20),cleanText(req.body.city??old.city,120),cleanText(req.body.notes??old.notes,2000),req.body.active===undefined?old.active:Boolean(req.body.active)]);
    res.json({provider:result.rows[0]});
  } catch(error){next(error);}
});

app.get('/api/work-orders', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization) return res.status(403).json({error:'Arbeitsaufträge sind im Hausverwaltungs-Arbeitsbereich verfügbar.'});
    const result=await pool.query(`SELECT wo.*,sp.company_name,sp.trade,sp.email AS provider_email,c.title AS case_title,c.property_label,c.location_label,p.name AS property_name,u.label AS unit_label
      FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id JOIN defect_cases c ON c.id=wo.case_id LEFT JOIN properties p ON p.id=c.property_id LEFT JOIN units u ON u.id=c.unit_id
      WHERE wo.organization_id=$1 ORDER BY wo.updated_at DESC`,[organization.id]);
    res.json({orders:result.rows});
  } catch(error){next(error);}
});

app.get('/api/cases/:caseId/work-orders', auth, async (req,res,next)=>{
  try {
    const accessible=await canAccessCase(req.user.id,req.params.caseId);
    if(!accessible) return res.status(404).json({error:'Mangel nicht gefunden.'});
    const organization=await organizationForUser(req.user.id);
    if(!organization || accessible.organization_id!==organization.id) return res.json({orders:[],providers:[]});
    const [orders,providers]=await Promise.all([
      pool.query(`SELECT wo.*,sp.company_name,sp.trade,sp.email AS provider_email FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id WHERE wo.case_id=$1 AND wo.organization_id=$2 ORDER BY wo.created_at DESC`,[req.params.caseId,organization.id]),
      pool.query(`SELECT id,company_name,trade,email,phone FROM service_providers WHERE organization_id=$1 AND active=true ORDER BY company_name`,[organization.id])
    ]);
    res.json({orders:orders.rows,providers:providers.rows});
  } catch(error){next(error);}
});

app.post('/api/cases/:caseId/work-orders', auth, async (req,res,next)=>{
  const client=await pool.connect();
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization) return res.status(403).json({error:'Nur Hausverwaltungen können Arbeitsaufträge erstellen.'});
    const accessible=await canAccessCase(req.user.id,req.params.caseId);
    if(!accessible || accessible.organization_id!==organization.id) return res.status(404).json({error:'Vorgang nicht gefunden.'});
    const provider=await providerForOrganization(cleanText(req.body.providerId,80),organization.id);
    if(!provider) return res.status(400).json({error:'Bitte wähle einen gültigen Dienstleister.'});
    const title=cleanText(req.body.title,180)||accessible.title;
    const description=cleanText(req.body.description,6000)||accessible.description;
    const token=crypto.randomBytes(32).toString('base64url'); const orderId=id();
    await client.query('BEGIN');
    const result=await client.query(`INSERT INTO work_orders (id,organization_id,case_id,provider_id,created_by,title,description,status,due_on,token_hash,token_expires_at)
      VALUES ($1,$2,$3,$4,$5,$6,$7,'draft',$8,$9,now()+interval '30 days') RETURNING *`,[orderId,organization.id,req.params.caseId,provider.id,req.user.id,title,description,req.body.dueOn||null,tokenHash(token)]);
    const portalUrl=contractorUrl(token); let delivery='manual';
    try { if(await sendWorkOrderMail({provider,organization,item:result.rows[0],portalUrl})) delivery='email'; } catch(mailError){ console.error('Work order mail failed',mailError); }
    const status=delivery==='email'?'sent':'draft';
    await client.query(`UPDATE work_orders SET status=$2,sent_at=CASE WHEN $2='sent' THEN now() ELSE NULL END,updated_at=now() WHERE id=$1`,[orderId,status]);
    await client.query(`INSERT INTO case_events (id,case_id,user_id,event_type,note,visibility) VALUES ($1,$2,$3,'note',$4,'internal')`,[id(),req.params.caseId,req.user.id,`Arbeitsauftrag an ${provider.company_name} erstellt${delivery==='email'?' und per E-Mail versendet':''}.`]);
    await client.query('COMMIT');
    res.status(201).json({order:{...result.rows[0],status,company_name:provider.company_name},portalUrl,delivery});
  } catch(error){await client.query('ROLLBACK');next(error);} finally{client.release();}
});

app.post('/api/work-orders/:orderId/send', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization) return res.status(403).json({error:'Nicht verfügbar.'});
    const result=await pool.query(`SELECT wo.*,sp.company_name,sp.email,sp.contact_name FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id WHERE wo.id=$1 AND wo.organization_id=$2`,[req.params.orderId,organization.id]);
    if(!result.rowCount) return res.status(404).json({error:'Arbeitsauftrag nicht gefunden.'});
    const order=result.rows[0]; if(!order.email) return res.status(400).json({error:'Beim Dienstleister ist keine E-Mail-Adresse hinterlegt.'});
    const token=crypto.randomBytes(32).toString('base64url'); const portalUrl=contractorUrl(token);
    await pool.query(`UPDATE work_orders SET token_hash=$2,token_expires_at=now()+interval '30 days',status='sent',sent_at=now(),updated_at=now() WHERE id=$1`,[order.id,tokenHash(token)]);
    await sendWorkOrderMail({provider:{email:order.email},organization,item:order,portalUrl});
    res.json({sent:true,portalUrl});
  } catch(error){next(error);}
});

app.get('/api/work-orders/:orderId/pdf', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization) return res.status(403).end();
    const result=await pool.query(`SELECT wo.*,sp.company_name,sp.contact_name,sp.street AS provider_street,sp.postal_code AS provider_postal_code,sp.city AS provider_city,sp.email AS provider_email,sp.phone AS provider_phone,c.title AS case_title,c.category,c.description AS case_description,c.property_label,c.location_label,p.name AS property_name,p.street AS property_street,p.postal_code AS property_postal_code,p.city AS property_city,u.label AS unit_label,o.name AS organization_name
      FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id JOIN defect_cases c ON c.id=wo.case_id JOIN organizations o ON o.id=wo.organization_id LEFT JOIN properties p ON p.id=c.property_id LEFT JOIN units u ON u.id=c.unit_id WHERE wo.id=$1 AND wo.organization_id=$2`,[req.params.orderId,organization.id]);
    if(!result.rowCount) return res.status(404).json({error:'Arbeitsauftrag nicht gefunden.'});
    const x=result.rows[0]; const doc=new PDFDocument({size:'A4',margins:{top:44,right:48,bottom:48,left:48}}); res.type('application/pdf'); res.setHeader('Content-Disposition',`attachment; filename="arbeitsauftrag-${x.id.split('-')[0]}.pdf"`); doc.pipe(res);
    doc.rect(0,0,doc.page.width,84).fill('#18212B'); doc.fillColor('#FFFFFF').font('Helvetica-Bold').fontSize(20).text('MängelFix',48,24); doc.font('Helvetica').fontSize(9).fillColor('#B9C1C8').text('ARBEITSAUFTRAG',48,52,{characterSpacing:1.2});
    doc.fillColor('#18212B').font('Helvetica-Bold').fontSize(17).text(x.title,48,112,{width:499}); doc.font('Helvetica').fontSize(9).fillColor('#66717D').text(`Auftrag ${x.id.split('-')[0].toUpperCase()} · erstellt ${new Date(x.created_at).toLocaleDateString('de-DE')}`,48,140);
    const box=(label,value,y)=>{doc.roundedRect(48,y,499,52,5).fill('#F4F6F8');doc.fillColor('#6F7A86').font('Helvetica-Bold').fontSize(7.5).text(label,60,y+10);doc.fillColor('#18212B').font('Helvetica-Bold').fontSize(10).text(value||'—',60,y+25,{width:470});};
    box('AUFTRAGGEBER',x.organization_name,174); box('AUFTRAGNEHMER',[x.company_name,x.contact_name].filter(Boolean).join(' · '),234); box('OBJEKT / EINSATZORT',[x.property_name||x.property_label,x.unit_label,x.location_label,[x.property_street,[x.property_postal_code,x.property_city].filter(Boolean).join(' ')].filter(Boolean).join(', ')].filter(Boolean).join(' · '),294);
    doc.fillColor('#2457D6').font('Helvetica-Bold').fontSize(8).text('AUFGABENBESCHREIBUNG',48,374,{characterSpacing:1}); doc.fillColor('#18212B').font('Helvetica').fontSize(10).text(x.description,48,394,{width:499,lineGap:3});
    const yy=Math.max(doc.y+24,500); doc.moveTo(48,yy).lineTo(547,yy).strokeColor('#DFE4E8').stroke(); doc.fillColor('#6F7A86').fontSize(8).text(`Gewünschte Erledigung: ${x.due_on?new Date(x.due_on).toLocaleDateString('de-DE'):'nicht festgelegt'}`,48,yy+14); doc.text('Rückmeldung und Status können über den persönlichen MängelFix-Auftragslink erfolgen.',48,yy+30,{width:499});
    doc.fontSize(7.5).fillColor('#7A8490').text('MängelFix · Arbeitsauftrag · Kamilunavo',48,doc.page.height-60,{width:499,align:'center'}); doc.end();
  } catch(error){next(error);}
});

app.get('/api/contractor/work-orders/:token', async (req,res,next)=>{
  try {
    const result=await pool.query(`SELECT wo.id,wo.title,wo.description,wo.status,wo.due_on,wo.scheduled_for,wo.contractor_note,wo.created_at,wo.token_expires_at,sp.company_name,sp.trade,o.name AS organization_name,c.property_label,c.location_label,p.name AS property_name,p.street AS property_street,p.postal_code AS property_postal_code,p.city AS property_city,u.label AS unit_label
      FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id JOIN organizations o ON o.id=wo.organization_id JOIN defect_cases c ON c.id=wo.case_id LEFT JOIN properties p ON p.id=c.property_id LEFT JOIN units u ON u.id=c.unit_id WHERE wo.token_hash=$1`,[tokenHash(req.params.token)]);
    if(!result.rowCount) return res.status(404).json({error:'Arbeitsauftrag nicht gefunden.'}); const order=result.rows[0];
    if(new Date(order.token_expires_at)<=new Date()) return res.status(410).json({error:'Dieser Auftragslink ist abgelaufen. Bitte wenden Sie sich an die Hausverwaltung.'});
    res.json({order});
  } catch(error){next(error);}
});

app.post('/api/contractor/work-orders/:token/status', async (req,res,next)=>{
  try {
    const status=cleanText(req.body.status,30); if(!['accepted','scheduled','completed','declined'].includes(status)) return res.status(400).json({error:'Ungültiger Auftragsstatus.'});
    const current=await pool.query(`SELECT wo.*,sp.company_name,o.name AS organization_name,c.title AS case_title FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id JOIN organizations o ON o.id=wo.organization_id JOIN defect_cases c ON c.id=wo.case_id WHERE wo.token_hash=$1`,[tokenHash(req.params.token)]);
    if(!current.rowCount) return res.status(404).json({error:'Arbeitsauftrag nicht gefunden.'}); const old=current.rows[0]; if(new Date(old.token_expires_at)<=new Date()) return res.status(410).json({error:'Dieser Auftragslink ist abgelaufen.'});
    const scheduledFor=req.body.scheduledFor?new Date(req.body.scheduledFor):old.scheduled_for; if(req.body.scheduledFor && isNaN(scheduledFor.getTime())) return res.status(400).json({error:'Ungültiger Termin.'});
    const result=await pool.query(`UPDATE work_orders SET status=$2,scheduled_for=$3,contractor_note=$4,accepted_at=CASE WHEN $2='accepted' AND accepted_at IS NULL THEN now() ELSE accepted_at END,completed_at=CASE WHEN $2='completed' THEN now() ELSE completed_at END,updated_at=now() WHERE id=$1 RETURNING *`,[old.id,status,scheduledFor||null,cleanText(req.body.note,3000)]);
    await pool.query(`INSERT INTO case_events (id,case_id,user_id,event_type,note,visibility) VALUES ($1,$2,$3,'note',$4,'internal')`,[id(),old.case_id,old.created_by,`Dienstleister ${old.company_name}: Auftrag ${status==='accepted'?'angenommen':status==='scheduled'?'terminiert':status==='completed'?'als erledigt gemeldet':'abgelehnt'}${req.body.note?` – ${cleanText(req.body.note,500)}`:''}.`]);
    res.json({order:result.rows[0]});
  } catch(error){next(error);}
});

'''
if "const workOrderStatuses" not in server:
    server = server.replace(anchor, server_block + anchor)
server_path.write_text(server)

# UI: insert contractor/work-order components before Workspace
workspace_anchor = 'function Workspace({ user, setUser, onLogout, navigate }) {'
ui_block = r'''

const tradeOptions=['SHK / Heizung / Sanitär','Elektro','Maler / Trockenbau','Fenster / Türen','Dach / Fassade','Schlüsseldienst','Reinigung / Trocknung','Hausmeister','Garten / Außenanlagen','Sonstiges'];
const orderStatusLabels={draft:'Entwurf',sent:'Versendet',accepted:'Angenommen',scheduled:'Termin geplant',completed:'Erledigt',declined:'Abgelehnt'};

function ProvidersView(){
  const [providers,setProviders]=useState([]); const [show,setShow]=useState(false); const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
  const [form,setForm]=useState({companyName:'',trade:tradeOptions[0],contactName:'',email:'',phone:'',street:'',postalCode:'',city:'',notes:''});
  async function load(){try{setProviders((await api('/api/providers')).providers)}catch(e){setError(e.message)}} useEffect(()=>{load()},[]);
  async function create(e){e.preventDefault();setBusy(true);setError('');try{await api('/api/providers',{method:'POST',body:JSON.stringify(form)});setShow(false);setForm({companyName:'',trade:tradeOptions[0],contactName:'',email:'',phone:'',street:'',postalCode:'',city:'',notes:''});await load()}catch(x){setError(x.message)}finally{setBusy(false)}}
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>DIENSTLEISTER</span><h1>Handwerker & Partnerfirmen</h1><p>Firmenstammdaten nach Gewerk verwalten und direkt für Arbeitsaufträge verwenden.</p></div><button className="workspacePrimary" onClick={()=>setShow(true)}>+ Dienstleister anlegen</button></div>{error&&<div className="errorBox">{error}</div>}<div className="providerGrid">{providers.length?providers.map(p=><article className="providerCard" key={p.id}><div className="providerTrade">{p.trade}</div><h2>{p.company_name}</h2><p>{p.contact_name||'Kein Ansprechpartner'}{p.email?` · ${p.email}`:''}</p><small>{[p.street,[p.postal_code,p.city].filter(Boolean).join(' ')].filter(Boolean).join(', ')||'Keine Anschrift'}</small><div className="providerStats"><span><b>{p.open_order_count}</b> offen</span><span><b>{p.order_count}</b> gesamt</span></div></article>):<div className="emptyCard workspaceEmpty">Noch keine Dienstleister angelegt.</div>}</div>{show&&<div className="modalBackdrop" onMouseDown={()=>setShow(false)}><div className="modal proModal" onMouseDown={e=>e.stopPropagation()}><div className="modalHeader"><div><div className="eyebrow">NEUER DIENSTLEISTER</div><h2>Firma anlegen</h2></div><button className="iconButton" onClick={()=>setShow(false)}>×</button></div><form className="caseForm" onSubmit={create}><div className="formGrid two"><label>Firma<input required value={form.companyName} onChange={e=>setForm({...form,companyName:e.target.value})}/></label><label>Gewerk<select value={form.trade} onChange={e=>setForm({...form,trade:e.target.value})}>{tradeOptions.map(x=><option key={x}>{x}</option>)}</select></label><label>Ansprechpartner<input value={form.contactName} onChange={e=>setForm({...form,contactName:e.target.value})}/></label><label>E-Mail<input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label><label>Telefon<input value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/></label><label>Straße<input value={form.street} onChange={e=>setForm({...form,street:e.target.value})}/></label><label>PLZ<input value={form.postalCode} onChange={e=>setForm({...form,postalCode:e.target.value})}/></label><label>Ort<input value={form.city} onChange={e=>setForm({...form,city:e.target.value})}/></label></div><label>Interne Notiz<textarea rows="3" value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></label>{error&&<div className="errorBox">{error}</div>}<div className="modalActions"><button type="button" className="secondaryButton" onClick={()=>setShow(false)}>Abbrechen</button><button className="primaryButton" disabled={busy}>{busy?'Speichern…':'Dienstleister speichern'}</button></div></form></div></div>}</div>;
}

function WorkOrdersView({onSelectCase}){
  const [orders,setOrders]=useState([]); const [error,setError]=useState(''); useEffect(()=>{api('/api/work-orders').then(d=>setOrders(d.orders)).catch(e=>setError(e.message))},[]);
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>ARBEITSAUFTRÄGE</span><h1>Beauftragte Dienstleister</h1><p>Versand, Annahme, Termine und Rückmeldungen aus einem Vorgang heraus nachvollziehen.</p></div></div>{error&&<div className="errorBox">{error}</div>}<div className="orderList">{orders.length?orders.map(o=><article className="orderRow" key={o.id}><div className="orderMark">A</div><div><span>{o.trade}</span><h3>{o.title}</h3><p>{o.company_name} · {o.property_name||o.property_label||'ohne Objekt'}{o.unit_label?` · ${o.unit_label}`:''}</p></div><span className={`orderStatus order-${o.status}`}>{orderStatusLabels[o.status]||o.status}</span><div className="orderRowActions"><a href={`/api/work-orders/${o.id}/pdf`} target="_blank" rel="noreferrer">PDF</a><button onClick={()=>onSelectCase(o.case_id)}>Vorgang →</button></div></article>):<div className="emptyCard workspaceEmpty">Noch keine Arbeitsaufträge vorhanden. Öffne einen Mangel und beauftrage dort einen Dienstleister.</div>}</div></div>;
}

function WorkOrderPanel({caseId}){
  const [data,setData]=useState(null); const [show,setShow]=useState(false); const [error,setError]=useState(''); const [busy,setBusy]=useState(false); const [result,setResult]=useState(null);
  const [form,setForm]=useState({providerId:'',title:'',description:'',dueOn:''});
  async function load(){try{setData(await api(`/api/cases/${caseId}/work-orders`))}catch(e){setData({orders:[],providers:[]})}} useEffect(()=>{load()},[caseId]);
  if(!data || (!data.providers.length&&!data.orders.length)) return data&&data.providers.length===0?<section className="contentCard contractorEmpty"><div className="cardKicker">DIENSTLEISTER</div><h3>Noch keine Partnerfirma hinterlegt</h3><p className="muted">Lege zuerst unter „Dienstleister“ eine Firma an, danach kannst du aus diesem Mangel einen Arbeitsauftrag erstellen.</p></section>:null;
  async function create(e){e.preventDefault();setBusy(true);setError('');setResult(null);try{const d=await api(`/api/cases/${caseId}/work-orders`,{method:'POST',body:JSON.stringify(form)});setResult(d);setShow(false);setForm({providerId:'',title:'',description:'',dueOn:''});await load()}catch(x){setError(x.message)}finally{setBusy(false)}}
  return <section className="contentCard workOrderPanel"><div className="sectionTitle"><div><div className="cardKicker">ARBEITSAUFTRÄGE</div><h3>Dienstleister beauftragen</h3><p className="muted">Auftrag als PDF und – bei eingerichtetem SMTP – direkt per E-Mail mit persönlichem Rückmeldelink senden.</p></div><button className="secondaryButton" onClick={()=>setShow(true)}>+ Arbeitsauftrag</button></div>{result&&<div className="successBox">Arbeitsauftrag erstellt. {result.delivery==='email'?'E-Mail wurde versendet.':'SMTP ist noch nicht aktiv – Link kann manuell geteilt werden.'}</div>}<div className="caseOrders">{data.orders.length?data.orders.map(o=><div className="caseOrder" key={o.id}><div><span>{o.trade}</span><b>{o.company_name}</b><small>{o.title}</small></div><span className={`orderStatus order-${o.status}`}>{orderStatusLabels[o.status]||o.status}</span><a href={`/api/work-orders/${o.id}/pdf`} target="_blank" rel="noreferrer">PDF</a></div>):<div className="emptyMini">Noch kein Dienstleister beauftragt.</div>}</div>{show&&<div className="modalBackdrop" onMouseDown={()=>setShow(false)}><div className="modal proModal" onMouseDown={e=>e.stopPropagation()}><div className="modalHeader"><div><div className="eyebrow">ARBEITSAUFTRAG</div><h2>Dienstleister beauftragen</h2></div><button className="iconButton" onClick={()=>setShow(false)}>×</button></div><form className="caseForm" onSubmit={create}><label>Dienstleister<select required value={form.providerId} onChange={e=>setForm({...form,providerId:e.target.value})}><option value="">Firma auswählen…</option>{data.providers.map(p=><option key={p.id} value={p.id}>{p.company_name} · {p.trade}</option>)}</select></label><label>Auftragstitel<input required placeholder="z. B. Heizungsanlage prüfen und instand setzen" value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label><label>Aufgabenbeschreibung<textarea required rows="6" placeholder="Was soll geprüft bzw. ausgeführt werden?" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></label><label>Gewünschte Erledigung <em>optional</em><input type="date" value={form.dueOn} onChange={e=>setForm({...form,dueOn:e.target.value})}/></label>{error&&<div className="errorBox">{error}</div>}<div className="modalActions"><button type="button" className="secondaryButton" onClick={()=>setShow(false)}>Abbrechen</button><button className="primaryButton" disabled={busy}>{busy?'Erstellen…':'Auftrag erstellen & senden'}</button></div></form></div></div>}</section>;
}

function ContractorPortal({token,navigate}){
  const [data,setData]=useState(null); const [error,setError]=useState(''); const [busy,setBusy]=useState(false); const [note,setNote]=useState(''); const [scheduledFor,setScheduledFor]=useState('');
  async function load(){try{setData(await api(`/api/contractor/work-orders/${token}`))}catch(e){setError(e.message)}} useEffect(()=>{load()},[token]);
  async function setStatus(status){setBusy(true);setError('');try{await api(`/api/contractor/work-orders/${token}/status`,{method:'POST',body:JSON.stringify({status,note,scheduledFor:status==='scheduled'?scheduledFor:null})});setNote('');await load()}catch(e){setError(e.message)}finally{setBusy(false)}}
  return <div className="contractorPortal"><header><Logo inverse/><span>EXTERNER ARBEITSAUFTRAG</span></header><main>{error?<div className="contractorError"><h1>Arbeitsauftrag nicht verfügbar</h1><p>{error}</p></div>:!data?<div className="contractorLoading">Arbeitsauftrag wird geladen…</div>:<><div className="contractorHero"><div><span>{data.order.trade}</span><h1>{data.order.title}</h1><p>Auftraggeber: <b>{data.order.organization_name}</b> · Auftragnehmer: <b>{data.order.company_name}</b></p></div><span className={`orderStatus order-${data.order.status}`}>{orderStatusLabels[data.order.status]||data.order.status}</span></div><div className="contractorGrid"><section><h3>Aufgabenbeschreibung</h3><p className="contractorDescription">{data.order.description}</p><dl><dt>Objekt</dt><dd>{data.order.property_name||data.order.property_label||'—'}</dd><dt>Einheit / Raum</dt><dd>{[data.order.unit_label,data.order.location_label].filter(Boolean).join(' · ')||'—'}</dd><dt>Adresse</dt><dd>{[data.order.property_street,[data.order.property_postal_code,data.order.property_city].filter(Boolean).join(' ')].filter(Boolean).join(', ')||'—'}</dd><dt>Gewünschte Erledigung</dt><dd>{fmtDate(data.order.due_on)}</dd></dl></section><aside><h3>Rückmeldung</h3><p>Bitte aktualisieren Sie den Auftrag direkt hier. Dafür ist kein MängelFix-Konto erforderlich.</p><label>Notiz<textarea rows="4" value={note} onChange={e=>setNote(e.target.value)} placeholder="z. B. Ersatzteil bestellt…"/></label><label>Termin<input type="datetime-local" value={scheduledFor} onChange={e=>setScheduledFor(e.target.value)}/></label><div className="contractorActions"><button disabled={busy} onClick={()=>setStatus('accepted')}>Auftrag annehmen</button><button disabled={busy||!scheduledFor} onClick={()=>setStatus('scheduled')}>Termin bestätigen</button><button disabled={busy} className="complete" onClick={()=>setStatus('completed')}>Als erledigt melden</button><button disabled={busy} className="decline" onClick={()=>setStatus('declined')}>Auftrag ablehnen</button></div>{data.order.contractor_note&&<div className="lastContractorNote"><b>Letzte Rückmeldung</b><p>{data.order.contractor_note}</p></div>}</aside></div></>}</main><footer>Dieser Link gewährt ausschließlich Zugriff auf den angezeigten Arbeitsauftrag.</footer></div>;
}

'''
if 'function ProvidersView()' not in app:
    app = app.replace(workspace_anchor, ui_block + workspace_anchor)

# Add work order panel after assignment panel in case detail
needle = '<AssignmentPanel caseId={caseId} item={item} onChanged={async()=>{await load();onUpdated();}} />'
if '<WorkOrderPanel caseId={caseId}/>' not in app:
    app = app.replace(needle, needle + "\n      {data.viewerRole==='management'&&<WorkOrderPanel caseId={caseId}/>}")

# Workspace view routing
app = app.replace("else if (view === 'team') content = <TeamView />;", "else if (view === 'providers') content = <ProvidersView />;\n  else if (view === 'orders') content = <WorkOrdersView onSelectCase={setSelected} />;\n  else if (view === 'team') content = <TeamView />;")

# Sidebar buttons before Team
sidebar_needle = "<button className={view === 'team' ? 'active' : ''} onClick={() => { setSelected(null); setView('team'); }}><span>T</span>{management?.organization ? 'Team' : 'Verwaltung'}</button>"
sidebar_repl = "{management?.organization&&<><button className={view === 'providers' ? 'active' : ''} onClick={() => { setSelected(null); setView('providers'); }}><span>H</span>Dienstleister</button><button className={view === 'orders' ? 'active' : ''} onClick={() => { setSelected(null); setView('orders'); }}><span>A</span>Aufträge</button></>}" + sidebar_needle
if "setView('providers')" not in app:
    app = app.replace(sidebar_needle, sidebar_repl)

# Public contractor route before app route
route_needle = "if (path.startsWith('/einladung/')) return <InvitationPage token={path.split('/').pop()} user={state.user} navigate={navigate} />;"
if "path.startsWith('/auftrag/')" not in app:
    app = app.replace(route_needle, route_needle + "\n  if (path.startsWith('/auftrag/')) return <ContractorPortal token={path.split('/').pop()} navigate={navigate} />;")
app_path.write_text(app)

css_block = r'''

/* v0.8 – Dienstleister & Arbeitsaufträge */
.providerGrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}.providerCard{background:#fff;border:1px solid #e0e5e9;border-radius:10px;padding:22px;box-shadow:0 4px 18px rgba(24,33,43,.04)}.providerTrade{display:inline-flex;background:#eef3ff;color:#2457d6;font-size:11px;font-weight:800;letter-spacing:.06em;padding:6px 9px;border-radius:4px}.providerCard h2{margin:14px 0 6px}.providerCard p,.providerCard small{color:#68737e}.providerStats{display:flex;gap:22px;border-top:1px solid #edf0f2;margin-top:18px;padding-top:14px}.providerStats span{font-size:12px;color:#75808b}.providerStats b{font-size:16px;color:#18212b;margin-right:4px}.orderList{display:flex;flex-direction:column;gap:10px}.orderRow{display:grid;grid-template-columns:42px 1fr auto auto;gap:16px;align-items:center;background:#fff;border:1px solid #e1e5e9;border-radius:8px;padding:16px 18px}.orderMark{width:38px;height:38px;display:grid;place-items:center;border-radius:7px;background:#18212b;color:#fff;font-weight:800}.orderRow h3{margin:3px 0}.orderRow>div:nth-child(2)>span{font-size:10px;font-weight:800;color:#2457d6;letter-spacing:.08em}.orderRow p{margin:0;color:#717c87;font-size:13px}.orderStatus{display:inline-flex;align-items:center;justify-content:center;white-space:nowrap;border-radius:4px;padding:7px 9px;font-size:10px;font-weight:800;letter-spacing:.05em;background:#eef1f4;color:#53606d}.order-sent{background:#e9f0ff;color:#2457d6}.order-accepted{background:#ebf7f2;color:#167452}.order-scheduled{background:#fff5df;color:#8a6200}.order-completed{background:#e7f7ec;color:#1d7139}.order-declined{background:#ffebeb;color:#a83434}.orderRowActions{display:flex;gap:8px}.orderRowActions a,.orderRowActions button{border:1px solid #d9dfe4;background:#fff;border-radius:5px;padding:8px 10px;color:#26323e;text-decoration:none;font-weight:700;cursor:pointer}.caseOrders{display:flex;flex-direction:column;gap:8px}.caseOrder{display:grid;grid-template-columns:1fr auto auto;gap:14px;align-items:center;border:1px solid #e5e9ec;padding:12px 14px;border-radius:7px}.caseOrder>div{display:flex;flex-direction:column}.caseOrder>div span{font-size:10px;color:#2457d6;font-weight:800}.caseOrder small{color:#727e89}.caseOrder>a{font-weight:800;color:#2457d6}.contractorEmpty{border-left:4px solid #e4a11b}.contractorPortal{min-height:100vh;background:#f2f4f6;color:#18212b}.contractorPortal>header{height:82px;background:#18212b;display:flex;align-items:center;justify-content:space-between;padding:0 max(28px,calc((100vw - 1120px)/2));color:#aeb8c1;font-size:11px;font-weight:800;letter-spacing:.1em}.contractorPortal>main{max-width:1120px;margin:0 auto;padding:48px 28px 70px}.contractorHero{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:25px}.contractorHero>div>span{font-size:11px;color:#2457d6;font-weight:800;letter-spacing:.09em}.contractorHero h1{font-size:36px;margin:7px 0 10px}.contractorHero p{color:#65717c}.contractorGrid{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(310px,.7fr);gap:20px}.contractorGrid>section,.contractorGrid>aside{background:#fff;border:1px solid #dfe4e8;border-radius:10px;padding:26px}.contractorDescription{white-space:pre-wrap;line-height:1.65}.contractorGrid dl{display:grid;grid-template-columns:160px 1fr;border-top:1px solid #e5e9ec;margin-top:25px;padding-top:18px;gap:10px}.contractorGrid dt{color:#75808b}.contractorGrid dd{margin:0;font-weight:700}.contractorGrid label{display:flex;flex-direction:column;gap:7px;font-weight:700;margin:14px 0}.contractorGrid textarea,.contractorGrid input{border:1px solid #ccd4db;border-radius:6px;padding:11px;font:inherit}.contractorActions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:16px}.contractorActions button{border:0;border-radius:6px;padding:12px 9px;background:#2457d6;color:#fff;font-weight:800;cursor:pointer}.contractorActions .complete{background:#167452}.contractorActions .decline{background:#fff;color:#a83434;border:1px solid #e5baba}.lastContractorNote{margin-top:18px;padding:14px;background:#f5f7f8;border-radius:6px}.lastContractorNote p{margin-bottom:0}.contractorPortal>footer{text-align:center;padding:20px;color:#77828c;font-size:12px}.contractorError,.contractorLoading{max-width:680px;margin:60px auto;background:#fff;padding:30px;border-radius:10px;border:1px solid #dfe4e8}@media(max-width:850px){.orderRow{grid-template-columns:38px 1fr}.orderRow>.orderStatus,.orderRowActions{grid-column:2}.contractorGrid{grid-template-columns:1fr}.contractorHero{flex-direction:column}.contractorActions{grid-template-columns:1fr}.contractorGrid dl{grid-template-columns:1fr}.contractorPortal>header{padding:0 20px}}
'''
if '/* v0.8 – Dienstleister & Arbeitsaufträge */' not in css:
    css += css_block
css_path.write_text(css)
print('v0.8 applied')
