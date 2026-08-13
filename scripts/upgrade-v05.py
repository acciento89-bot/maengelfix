from pathlib import Path
import re

root = Path('.')
schema_p = root/'server/schema.sql'
server_p = root/'server/index.js'
app_p = root/'client/src/App.jsx'
css_p = root/'client/src/maengelfix-pro.css'

schema = schema_p.read_text()
if '-- v0.5:' not in schema:
    schema += r'''

-- v0.5: erweiterte Verwaltungs-Stammdaten
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS street text;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS postal_code text;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS city text;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS notes text;
ALTER TABLE units ADD COLUMN IF NOT EXISTS notes text;
'''
schema_p.write_text(schema)

server = server_p.read_text()
server = server.replace("version: '0.4.0'", "version: '0.5.0'")

marker = "app.get('/api/properties', auth, async (req, res, next) => {"
if "app.get('/api/management/overview'" not in server:
    block = r'''
app.get('/api/management/overview', auth, async (req, res, next) => {
  try {
    const organization = await organizationForUser(req.user.id);
    if (!organization) return res.json({ organization: null });
    const [propertyCount, unitCount, contactCount, cases, members] = await Promise.all([
      pool.query('SELECT count(*)::int AS count FROM properties WHERE organization_id=$1', [organization.id]),
      pool.query('SELECT count(*)::int AS count FROM units u JOIN properties p ON p.id=u.property_id WHERE p.organization_id=$1', [organization.id]),
      pool.query('SELECT count(*)::int AS count FROM contacts WHERE organization_id=$1', [organization.id]),
      pool.query(`SELECT c.id,c.title,c.status,c.deadline_on,c.assigned_user_id,p.name AS property_name,u.label AS unit_label,au.name AS assigned_user_name
        FROM defect_cases c LEFT JOIN properties p ON p.id=c.property_id LEFT JOIN units u ON u.id=c.unit_id LEFT JOIN users au ON au.id=c.assigned_user_id
        WHERE c.organization_id=$1 ORDER BY c.updated_at DESC`, [organization.id]),
      pool.query(`SELECT usr.id,usr.name,om.role,
        (SELECT count(*)::int FROM defect_cases c WHERE c.organization_id=$1 AND c.assigned_user_id=usr.id AND c.status<>'resolved') AS open_cases
        FROM organization_memberships om JOIN users usr ON usr.id=om.user_id WHERE om.organization_id=$1 ORDER BY usr.name`, [organization.id])
    ]);
    const rows = cases.rows;
    const now = new Date(); now.setHours(0,0,0,0);
    const overdue = rows.filter(c => c.deadline_on && c.status !== 'resolved' && new Date(c.deadline_on) < now).length;
    res.json({ organization, metrics: {
      properties: propertyCount.rows[0].count, units: unitCount.rows[0].count, contacts: contactCount.rows[0].count,
      open: rows.filter(c=>c.status!=='resolved').length, unassigned: rows.filter(c=>c.status!=='resolved'&&!c.assigned_user_id).length, overdue
    }, recent: rows.slice(0,6), members: members.rows });
  } catch (error) { next(error); }
});

app.get('/api/management/options', auth, async (req, res, next) => {
  try {
    const organization = await organizationForUser(req.user.id);
    if (!organization) return res.json({ organization: null, properties: [], members: [] });
    const [properties, members] = await Promise.all([
      pool.query(`SELECT p.id,p.name,p.street,p.postal_code,p.city,
        COALESCE(json_agg(json_build_object('id',u.id,'label',u.label,'floor',u.floor,'positionLabel',u.position_label) ORDER BY u.label) FILTER (WHERE u.id IS NOT NULL),'[]') AS units
        FROM properties p LEFT JOIN units u ON u.property_id=p.id WHERE p.organization_id=$1 GROUP BY p.id ORDER BY p.name`, [organization.id]),
      pool.query(`SELECT u.id,u.name,om.role FROM organization_memberships om JOIN users u ON u.id=om.user_id WHERE om.organization_id=$1 ORDER BY u.name`, [organization.id])
    ]);
    res.json({ organization, properties: properties.rows, members: members.rows });
  } catch (error) { next(error); }
});

'''
    server = server.replace(marker, block + marker)

if "app.get('/api/units/:unitId'" not in server:
    unit_marker = "app.get('/api/contacts', auth, async (req, res, next) => {"
    unit_block = r'''
app.get('/api/units/:unitId', auth, async (req, res, next) => {
  try {
    const { organizationId } = await scopeForUser(req.user.id);
    const unit = await pool.query(`SELECT u.*,p.name AS property_name,p.street AS property_street,p.postal_code AS property_postal_code,p.city AS property_city
      FROM units u JOIN properties p ON p.id=u.property_id WHERE u.id=$1 AND (($3::text IS NOT NULL AND p.organization_id=$3) OR ($3::text IS NULL AND p.organization_id IS NULL AND p.user_id=$2))`, [req.params.unitId, req.user.id, organizationId]);
    if (!unit.rowCount) return res.status(404).json({ error: 'Einheit nicht gefunden.' });
    const [contacts,cases] = await Promise.all([
      pool.query(`SELECT c.*,uc.role,uc.is_primary FROM unit_contacts uc JOIN contacts c ON c.id=uc.contact_id WHERE uc.unit_id=$1 ORDER BY uc.is_primary DESC,c.name`, [req.params.unitId]),
      pool.query(`SELECT c.*,au.name AS assigned_user_name FROM defect_cases c LEFT JOIN users au ON au.id=c.assigned_user_id WHERE c.unit_id=$1 ORDER BY c.updated_at DESC`, [req.params.unitId])
    ]);
    res.json({ unit: unit.rows[0], contacts: contacts.rows, cases: cases.rows });
  } catch (error) { next(error); }
});

app.delete('/api/units/:unitId/contacts/:contactId', auth, async (req,res,next)=>{
  try {
    const { organizationId } = await scopeForUser(req.user.id);
    const allowed = await pool.query(`SELECT 1 FROM units u JOIN properties p ON p.id=u.property_id WHERE u.id=$1 AND (($3::text IS NOT NULL AND p.organization_id=$3) OR ($3::text IS NULL AND p.organization_id IS NULL AND p.user_id=$2))`, [req.params.unitId, req.user.id, organizationId]);
    if (!allowed.rowCount) return res.status(404).json({error:'Einheit nicht gefunden.'});
    await pool.query('DELETE FROM unit_contacts WHERE unit_id=$1 AND contact_id=$2',[req.params.unitId,req.params.contactId]);
    res.status(204).end();
  } catch(error){ next(error); }
});

'''
    server = server.replace(unit_marker, unit_block + unit_marker)

server = server.replace(
"`INSERT INTO contacts (id,organization_id,user_id,name,email,phone,contact_type) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *`,\n      [id(), organizationId, req.user.id, name, cleanText(req.body.email,254)?.toLowerCase(), cleanText(req.body.phone,60), cleanText(req.body.contactType,40) || 'tenant']",
"`INSERT INTO contacts (id,organization_id,user_id,name,email,phone,contact_type,street,postal_code,city,notes) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING *`,\n      [id(), organizationId, req.user.id, name, cleanText(req.body.email,254)?.toLowerCase(), cleanText(req.body.phone,60), cleanText(req.body.contactType,40) || 'tenant', cleanText(req.body.street,180), cleanText(req.body.postalCode,20), cleanText(req.body.city,120), cleanText(req.body.notes,1200)]"
)

old_assign = re.compile(r"app\.patch\('/api/cases/:caseId/assignment'.*?\n\}\);", re.S)
new_assign = r'''app.patch('/api/cases/:caseId/assignment', auth, async (req, res, next) => {
  try {
    const accessible = await canAccessCase(req.user.id, req.params.caseId);
    if (!accessible) return res.status(404).json({ error: 'Mangel nicht gefunden.' });
    const organization = await organizationForUser(req.user.id);
    if (!organization) return res.status(403).json({ error: 'Zuweisungen sind nur im Verwaltungs-Arbeitsbereich verfügbar.' });
    const propertyId = cleanText(req.body.propertyId,80) || null;
    const unitId = cleanText(req.body.unitId,80) || null;
    const assignedUserId = cleanText(req.body.assignedUserId,80) || null;
    if (propertyId) {
      const p = await pool.query('SELECT 1 FROM properties WHERE id=$1 AND organization_id=$2',[propertyId,organization.id]);
      if (!p.rowCount) return res.status(400).json({error:'Objekt gehört nicht zu dieser Verwaltung.'});
    }
    if (unitId) {
      const u = await pool.query('SELECT 1 FROM units u JOIN properties p ON p.id=u.property_id WHERE u.id=$1 AND p.organization_id=$2 AND ($3::text IS NULL OR p.id=$3)',[unitId,organization.id,propertyId]);
      if (!u.rowCount) return res.status(400).json({error:'Einheit gehört nicht zum gewählten Objekt.'});
    }
    if (assignedUserId) {
      const m = await pool.query('SELECT 1 FROM organization_memberships WHERE organization_id=$1 AND user_id=$2',[organization.id,assignedUserId]);
      if (!m.rowCount) return res.status(400).json({error:'Mitarbeiter gehört nicht zu dieser Verwaltung.'});
    }
    const result = await pool.query(`UPDATE defect_cases SET property_id=$2, unit_id=$3, assigned_user_id=$4,
      property_label=COALESCE((SELECT name FROM properties WHERE id=$2),property_label),
      location_label=COALESCE((SELECT label FROM units WHERE id=$3),location_label), updated_at=now() WHERE id=$1 RETURNING *`, [req.params.caseId, propertyId, unitId, assignedUserId]);
    await pool.query('INSERT INTO case_events (id,case_id,user_id,event_type,note) VALUES ($1,$2,$3,$4,$5)',[id(),req.params.caseId,req.user.id,'assignment','Objekt, Einheit oder Zuständigkeit wurde aktualisiert.']);
    res.json({ case: result.rows[0] });
  } catch (error) { next(error); }
});'''
server = old_assign.sub(new_assign, server, count=1)

server = server.replace(
"`SELECT c.*,\n        (SELECT count(*)::int FROM attachments a WHERE a.case_id = c.id) AS attachment_count\n       FROM defect_cases c",
"`SELECT c.*, p.name AS property_name, un.label AS unit_name, au.name AS assigned_user_name,\n        (SELECT count(*)::int FROM attachments a WHERE a.case_id = c.id) AS attachment_count\n       FROM defect_cases c LEFT JOIN properties p ON p.id=c.property_id LEFT JOIN units un ON un.id=c.unit_id LEFT JOIN users au ON au.id=c.assigned_user_id"
)

server_p.write_text(server)

app = app_p.read_text()
app = app.replace('        <a href="/#tarife">Tarife</a>\n        <a href="/#tarife">Tarife</a>', '        <a href="/#tarife">Tarife</a>')

if 'function AssignmentPanel' not in app:
    insert_before = 'function CaseDetail({ caseId, onBack, onUpdated, user, onProfile }) {'
    component = r'''
function AssignmentPanel({ caseId, item, onChanged }) {
  const [options,setOptions]=useState(null); const [busy,setBusy]=useState(false); const [error,setError]=useState('');
  const [form,setForm]=useState({propertyId:item.property_id||'',unitId:item.unit_id||'',assignedUserId:item.assigned_user_id||''});
  useEffect(()=>{ api('/api/management/options').then(setOptions).catch(()=>setOptions({organization:null,properties:[],members:[]})); },[caseId]);
  if (!options || !options.organization) return null;
  const property=options.properties.find(p=>p.id===form.propertyId); const units=property?.units||[];
  async function save(){ setBusy(true);setError('');try{await api(`/api/cases/${caseId}/assignment`,{method:'PATCH',body:JSON.stringify(form)});await onChanged();}catch(e){setError(e.message);}finally{setBusy(false);} }
  return <section className="contentCard assignmentPanel"><div className="sectionTitle"><div><div className="cardKicker">VERWALTUNG</div><h3>Objekt & Zuständigkeit</h3><p className="muted">Ordne den Vorgang eindeutig einer Einheit und einem Mitarbeiter zu.</p></div></div><div className="formGrid three"><label>Objekt<select value={form.propertyId} onChange={e=>setForm({...form,propertyId:e.target.value,unitId:''})}><option value="">Nicht zugeordnet</option>{options.properties.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label>Einheit<select disabled={!form.propertyId} value={form.unitId} onChange={e=>setForm({...form,unitId:e.target.value})}><option value="">Keine Einheit</option>{units.map(u=><option key={u.id} value={u.id}>{u.label}</option>)}</select></label><label>Zuständig<select value={form.assignedUserId} onChange={e=>setForm({...form,assignedUserId:e.target.value})}><option value="">Nicht zugewiesen</option>{options.members.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select></label></div>{error&&<div className="errorBox">{error}</div>}<button className="secondaryButton" disabled={busy} onClick={save}>{busy?'Speichern…':'Zuordnung speichern'}</button></section>;
}

'''
    app = app.replace(insert_before, component + insert_before)

app = app.replace('</div>\n      <section className="contentCard"><div className="sectionTitle"><div><div className="cardKicker">BEWEISSICHERUNG</div>', '</div>\n      <AssignmentPanel caseId={caseId} item={item} onChanged={async()=>{await load();onUpdated();}} />\n      <section className="contentCard"><div className="sectionTitle"><div><div className="cardKicker">BEWEISSICHERUNG</div>', 1)

if 'function ManagementOverview' not in app:
    before = 'function OverviewView({ user, cases, onNew, onSelect, setView }) {'
    comp = r'''
function ManagementOverview({ user, cases, onNew, onSelect, setView, management }) {
  const m=management.metrics||{}; const recent=management.recent||[]; const members=management.members||[];
  return <div className="workspacePage managementHome"><div className="workspaceHeading"><div><span>VERWALTUNG</span><h1>{management.organization.name}</h1><p>Guten Morgen, {user.name.split(' ')[0]}. Hier siehst du Objekte, offene Vorgänge und Team-Auslastung auf einen Blick.</p></div><button className="workspacePrimary" onClick={onNew}>+ Mangel erfassen</button></div><div className="managementMetrics"><button onClick={()=>setView('objects')}><span>OBJEKTE</span><strong>{m.properties||0}</strong><small>{m.units||0} Einheiten</small></button><button onClick={()=>setView('cases')}><span>OFFENE MÄNGEL</span><strong>{m.open||0}</strong><small>{m.unassigned||0} ohne Zuständigkeit</small></button><button onClick={()=>setView('deadlines')} className={m.overdue?'attention':''}><span>ÜBERFÄLLIG</span><strong>{m.overdue||0}</strong><small>Fristen überschritten</small></button><button onClick={()=>setView('objects')}><span>KONTAKTE / MIETER</span><strong>{m.contacts||0}</strong><small>in der Verwaltung</small></button></div><div className="dashboardColumns managementColumns"><section className="workspacePanel"><div className="panelHead"><div><span>AKTUELLE VORGÄNGE</span><h2>Zuletzt bearbeitet</h2></div><button onClick={()=>setView('cases')}>Alle anzeigen →</button></div><CaseRows cases={recent.map(x=>({...x,attachment_count:0,property_label:x.property_name||x.unit_label||''}))} onSelect={onSelect} /></section><aside className="workspacePanel workloadPanel"><div className="panelHead"><div><span>TEAM</span><h2>Offene Zuständigkeiten</h2></div><button onClick={()=>setView('team')}>Team →</button></div>{members.map(member=><div className="workloadRow" key={member.id}><div>{member.name.slice(0,1).toUpperCase()}</div><span><b>{member.name}</b><small>{member.role==='owner'?'Inhaber':member.role==='admin'?'Admin':'Mitarbeiter'}</small></span><strong>{member.open_cases}</strong></div>)}</aside></div></div>;
}

'''
    app = app.replace(before, comp + before)

# Replace ManagedObjectsView as a whole
pattern = re.compile(r"function ManagedObjectsView\(\{ onSelect \}\) \{.*?\n\}\n\nfunction DeadlinesView", re.S)
new_managed = r'''function ManagedObjectsView({ onSelect }) {
  const [properties,setProperties]=useState([]); const [propertyId,setPropertyId]=useState(null); const [detail,setDetail]=useState(null); const [unitDetail,setUnitDetail]=useState(null);
  const [showNew,setShowNew]=useState(false); const [showUnit,setShowUnit]=useState(false); const [showContact,setShowContact]=useState(false); const [contacts,setContacts]=useState([]); const [error,setError]=useState('');
  const [form,setForm]=useState({name:'',street:'',postalCode:'',city:'',notes:''}); const [unitForm,setUnitForm]=useState({label:'',floor:'',positionLabel:'',areaSqm:''}); const [contactForm,setContactForm]=useState({name:'',email:'',phone:'',street:'',postalCode:'',city:'',notes:'',contactType:'tenant'});
  async function loadProperties(){try{setProperties((await api('/api/properties')).properties)}catch(e){setError(e.message)}}
  async function loadProperty(id){try{setDetail(await api(`/api/properties/${id}`));setPropertyId(id);setUnitDetail(null)}catch(e){setError(e.message)}}
  async function loadUnit(id){try{setUnitDetail(await api(`/api/units/${id}`));setContacts((await api('/api/contacts')).contacts)}catch(e){setError(e.message)}}
  useEffect(()=>{loadProperties()},[]);
  async function createProperty(e){e.preventDefault();try{const d=await api('/api/properties',{method:'POST',body:JSON.stringify(form)});setShowNew(false);setForm({name:'',street:'',postalCode:'',city:'',notes:''});await loadProperties();await loadProperty(d.property.id)}catch(x){setError(x.message)}}
  async function createUnit(e){e.preventDefault();try{const d=await api(`/api/properties/${propertyId}/units`,{method:'POST',body:JSON.stringify(unitForm)});setShowUnit(false);setUnitForm({label:'',floor:'',positionLabel:'',areaSqm:''});await loadProperty(propertyId);await loadUnit(d.unit.id)}catch(x){setError(x.message)}}
  async function createContact(e){e.preventDefault();try{const d=await api('/api/contacts',{method:'POST',body:JSON.stringify(contactForm)});await api(`/api/units/${unitDetail.unit.id}/contacts`,{method:'POST',body:JSON.stringify({contactId:d.contact.id,role:'tenant',isPrimary:unitDetail.contacts.length===0})});setShowContact(false);setContactForm({name:'',email:'',phone:'',street:'',postalCode:'',city:'',notes:'',contactType:'tenant'});await loadUnit(unitDetail.unit.id);await loadProperty(propertyId)}catch(x){setError(x.message)}}
  async function attachContact(contactId){try{await api(`/api/units/${unitDetail.unit.id}/contacts`,{method:'POST',body:JSON.stringify({contactId,role:'tenant',isPrimary:unitDetail.contacts.length===0})});await loadUnit(unitDetail.unit.id);await loadProperty(propertyId)}catch(x){setError(x.message)}}
  async function detachContact(contactId){try{await api(`/api/units/${unitDetail.unit.id}/contacts/${contactId}`,{method:'DELETE'});await loadUnit(unitDetail.unit.id);await loadProperty(propertyId)}catch(x){setError(x.message)}}

  if(unitDetail) { const u=unitDetail.unit; const available=contacts.filter(c=>!unitDetail.contacts.some(x=>x.id===c.id)); return <div className="workspacePage unitDetailPage"><button className="backButton" onClick={()=>setUnitDetail(null)}>← {u.property_name}</button><div className="workspaceHeading"><div><span>EINHEIT</span><h1>{u.label}</h1><p>{[u.floor,u.position_label,u.area_sqm?`${u.area_sqm} m²`:null].filter(Boolean).join(' · ')}</p></div><button className="workspacePrimary" onClick={()=>setShowContact(true)}>+ Mieter / Kontakt</button></div>{error&&<div className="errorBox">{error}</div>}<div className="unitDetailGrid"><section className="workspacePanel"><div className="panelHead"><div><span>MIETER & KONTAKTE</span><h2>{unitDetail.contacts.length} zugeordnet</h2></div></div>{unitDetail.contacts.length?unitDetail.contacts.map(c=><article className="tenantCard" key={c.id}><div className="tenantAvatar">{c.name.slice(0,1).toUpperCase()}</div><div><h3>{c.name}{c.is_primary&&<span>HAUPTKONTAKT</span>}</h3><p>{c.email||'Keine E-Mail'}{c.phone?` · ${c.phone}`:''}</p><small>{[c.street,[c.postal_code,c.city].filter(Boolean).join(' ')].filter(Boolean).join(', ')||'Keine Anschrift hinterlegt'}</small></div><button onClick={()=>detachContact(c.id)}>Entfernen</button></article>):<div className="emptyMini">Noch kein Mieter oder Kontakt zugeordnet.</div>}{available.length>0&&<div className="existingContact"><label>Vorhandenen Kontakt zuordnen<select defaultValue="" onChange={e=>{if(e.target.value)attachContact(e.target.value);e.target.value='';}}><option value="">Kontakt auswählen…</option>{available.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label></div>}</section><aside className="workspacePanel unitFacts"><div className="panelHead"><div><span>STAMMDATEN</span><h2>Einheit</h2></div></div><dl><dt>Objekt</dt><dd>{u.property_name}</dd><dt>Etage</dt><dd>{u.floor||'—'}</dd><dt>Lage</dt><dd>{u.position_label||'—'}</dd><dt>Fläche</dt><dd>{u.area_sqm?`${u.area_sqm} m²`:'—'}</dd></dl></aside></div><section className="workspacePanel"><div className="panelHead"><div><span>MÄNGEL</span><h2>Vorgänge dieser Einheit</h2></div></div><CaseRows cases={unitDetail.cases.map(x=>({...x,attachment_count:x.attachment_count||0}))} onSelect={onSelect} emptyText="Noch kein Mangel für diese Einheit." /></section>{showContact&&<div className="modalBackdrop" onMouseDown={()=>setShowContact(false)}><div className="modal proModal" onMouseDown={e=>e.stopPropagation()}><div className="modalHeader"><div><div className="eyebrow">NEUER KONTAKT</div><h2>Mieter / Kontakt anlegen</h2></div><button className="iconButton" onClick={()=>setShowContact(false)}>×</button></div><form className="caseForm" onSubmit={createContact}><label>Name<input required value={contactForm.name} onChange={e=>setContactForm({...contactForm,name:e.target.value})}/></label><div className="formGrid two"><label>E-Mail<input type="email" value={contactForm.email} onChange={e=>setContactForm({...contactForm,email:e.target.value})}/></label><label>Telefon<input value={contactForm.phone} onChange={e=>setContactForm({...contactForm,phone:e.target.value})}/></label><label>Straße<input value={contactForm.street} onChange={e=>setContactForm({...contactForm,street:e.target.value})}/></label><label>PLZ<input value={contactForm.postalCode} onChange={e=>setContactForm({...contactForm,postalCode:e.target.value})}/></label><label>Ort<input value={contactForm.city} onChange={e=>setContactForm({...contactForm,city:e.target.value})}/></label></div><label>Interne Notiz<textarea rows="3" value={contactForm.notes} onChange={e=>setContactForm({...contactForm,notes:e.target.value})}/></label><div className="modalActions"><button type="button" className="secondaryButton" onClick={()=>setShowContact(false)}>Abbrechen</button><button className="primaryButton">Kontakt anlegen & zuordnen</button></div></form></div></div>}</div> }

  if(propertyId&&detail) return <div className="workspacePage propertyDetailPage"><button className="backButton" onClick={()=>{setPropertyId(null);setDetail(null)}}>← Alle Objekte</button><div className="workspaceHeading"><div><span>OBJEKT</span><h1>{detail.property.name}</h1><p>{[detail.property.street,[detail.property.postal_code,detail.property.city].filter(Boolean).join(' ')].filter(Boolean).join(' · ')}</p></div><button className="workspacePrimary" onClick={()=>setShowUnit(true)}>+ Einheit anlegen</button></div><div className="metricGrid"><div><span>EINHEITEN</span><strong>{detail.units.length}</strong><small>Wohnungen / Gewerbe</small></div><div><span>VORGÄNGE</span><strong>{detail.cases.length}</strong><small>am Objekt</small></div><div><span>OFFEN</span><strong>{detail.cases.filter(x=>x.status!=='resolved').length}</strong><small>noch nicht erledigt</small></div><div><span>KONTAKTE</span><strong>{detail.units.reduce((n,u)=>n+Number(u.contact_count||0),0)}</strong><small>Einheiten-Zuordnungen</small></div></div><section className="workspacePanel"><div className="panelHead"><div><span>EINHEITEN</span><h2>Wohnungen & Bereiche</h2></div></div><div className="unitGrid proUnits">{detail.units.length?detail.units.map(u=><button className="unitCard" key={u.id} onClick={()=>loadUnit(u.id)}><span>EINHEIT</span><h3>{u.label}</h3><p>{[u.floor,u.position_label].filter(Boolean).join(' · ')||'Keine Zusatzangaben'}</p><div><b>{u.open_case_count}</b> offen · <b>{u.contact_count}</b> Kontakte</div><strong>→</strong></button>):<div className="emptyCard workspaceEmpty">Noch keine Einheiten angelegt.</div>}</div></section><section className="workspacePanel"><div className="panelHead"><div><span>VORGÄNGE</span><h2>Mängel am Objekt</h2></div></div><CaseRows cases={detail.cases} onSelect={onSelect} /></section>{showUnit&&<div className="modalBackdrop" onMouseDown={()=>setShowUnit(false)}><div className="modal proModal" onMouseDown={e=>e.stopPropagation()}><div className="modalHeader"><div><div className="eyebrow">NEUE EINHEIT</div><h2>Wohnung / Einheit anlegen</h2></div><button className="iconButton" onClick={()=>setShowUnit(false)}>×</button></div><form className="caseForm" onSubmit={createUnit}><label>Bezeichnung<input required placeholder="z. B. EG links / WE 01" value={unitForm.label} onChange={e=>setUnitForm({...unitForm,label:e.target.value})}/></label><div className="formGrid two"><label>Etage<input value={unitForm.floor} onChange={e=>setUnitForm({...unitForm,floor:e.target.value})}/></label><label>Lage<input value={unitForm.positionLabel} onChange={e=>setUnitForm({...unitForm,positionLabel:e.target.value})}/></label><label>Fläche m²<input type="number" step="0.1" value={unitForm.areaSqm} onChange={e=>setUnitForm({...unitForm,areaSqm:e.target.value})}/></label></div><div className="modalActions"><button type="button" className="secondaryButton" onClick={()=>setShowUnit(false)}>Abbrechen</button><button className="primaryButton">Einheit speichern</button></div></form></div></div>}</div>;

  return <div className="workspacePage"><div className="workspaceHeading"><div><span>OBJEKTE</span><h1>Gebäude & Liegenschaften</h1><p>Objekte, Einheiten, Mieter und Vorgänge zentral verwalten.</p></div><button className="workspacePrimary" onClick={()=>setShowNew(true)}>+ Objekt anlegen</button></div>{error&&<div className="errorBox">{error}</div>}<div className="managedObjectGrid">{properties.length?properties.map(p=><button className="managedObjectCard" key={p.id} onClick={()=>loadProperty(p.id)}><div className="managedObjectIcon">⌂</div><div><span>OBJEKT</span><h2>{p.name}</h2><p>{[p.street,[p.postal_code,p.city].filter(Boolean).join(' ')].filter(Boolean).join(' · ')||'Keine Adresse hinterlegt'}</p></div><div className="managedObjectStats"><span><b>{p.unit_count}</b> Einheiten</span><span><b>{p.open_case_count}</b> offen</span></div><strong>→</strong></button>):<div className="emptyCard workspaceEmpty">Noch kein Objekt angelegt.</div>}</div>{showNew&&<div className="modalBackdrop" onMouseDown={()=>setShowNew(false)}><div className="modal proModal" onMouseDown={e=>e.stopPropagation()}><div className="modalHeader"><div><div className="eyebrow">NEUES OBJEKT</div><h2>Gebäude anlegen</h2></div><button className="iconButton" onClick={()=>setShowNew(false)}>×</button></div><form className="caseForm" onSubmit={createProperty}><label>Objektname<input required value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label><label>Straße & Hausnummer<input value={form.street} onChange={e=>setForm({...form,street:e.target.value})}/></label><div className="formGrid two"><label>PLZ<input value={form.postalCode} onChange={e=>setForm({...form,postalCode:e.target.value})}/></label><label>Ort<input value={form.city} onChange={e=>setForm({...form,city:e.target.value})}/></label></div><label>Interne Notiz<textarea rows="3" value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></label><div className="modalActions"><button type="button" className="secondaryButton" onClick={()=>setShowNew(false)}>Abbrechen</button><button className="primaryButton">Objekt speichern</button></div></form></div></div>}</div>;
}

function DeadlinesView'''
app = pattern.sub(new_managed, app, count=1)

# Workspace management state
app = app.replace("const [view, setView] = useState('overview');", "const [view, setView] = useState('overview');\n  const [management,setManagement]=useState(undefined);")
app = app.replace("useEffect(() => { loadCases(); }, []);", "useEffect(() => { loadCases(); api('/api/management/overview').then(setManagement).catch(()=>setManagement({organization:null})); }, []);")
app = app.replace("else if (view === 'overview') content = <OverviewView user={user} cases={cases} onNew={() => setShowNew(true)} onSelect={setSelected} setView={setView} />;", "else if (view === 'overview') content = management?.organization ? <ManagementOverview user={user} cases={cases} onNew={() => setShowNew(true)} onSelect={setSelected} setView={setView} management={management} /> : <OverviewView user={user} cases={cases} onNew={() => setShowNew(true)} onSelect={setSelected} setView={setView} />;")
app = app.replace("else if (view === 'objects') content = <ManagedObjectsView onSelect={setSelected} />;", "else if (view === 'objects') content = management?.organization ? <ManagedObjectsView onSelect={setSelected} /> : <ObjectsView cases={cases} onSelect={setSelected} />;")
app = app.replace('<span>T</span>Team</button>', '<span>T</span>{management?.organization ? \'Team\' : \'Verwaltung\'}</button>')

app_p.write_text(app)

css = css_p.read_text()
if '/* v0.5 management */' not in css:
    css += r'''

/* v0.5 management */
.managementMetrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:22px 0}.managementMetrics>button{background:var(--surface);border:1px solid var(--line);padding:20px;text-align:left;box-shadow:var(--shadow-sm);border-radius:8px}.managementMetrics span,.managementMetrics small{display:block;color:var(--muted);font-size:11px}.managementMetrics strong{display:block;font-size:32px;margin:7px 0;color:var(--ink)}.managementMetrics .attention{border-color:#e7b65a;background:#fffaf0}.workloadPanel{height:max-content}.workloadRow{display:grid;grid-template-columns:38px 1fr auto;gap:10px;align-items:center;padding:12px 0;border-bottom:1px solid var(--line)}.workloadRow>div,.tenantAvatar{width:36px;height:36px;border-radius:8px;background:var(--ink);color:white;display:grid;place-items:center;font-weight:800}.workloadRow span b,.workloadRow span small{display:block}.workloadRow span small{color:var(--muted);font-size:11px}.workloadRow>strong{font-size:20px}.assignmentPanel{margin-top:18px}.formGrid.three{grid-template-columns:repeat(3,minmax(0,1fr))}.unitDetailGrid{display:grid;grid-template-columns:minmax(0,2fr) minmax(260px,1fr);gap:18px;margin-bottom:18px}.tenantCard{display:grid;grid-template-columns:44px 1fr auto;gap:12px;align-items:center;padding:14px 0;border-bottom:1px solid var(--line)}.tenantCard h3{margin:0 0 4px}.tenantCard h3 span{font-size:9px;margin-left:8px;padding:3px 6px;background:var(--blue-soft);color:var(--blue);border-radius:4px}.tenantCard p,.tenantCard small{margin:0;color:var(--muted)}.tenantCard button{border:0;background:transparent;color:#a33;cursor:pointer}.unitFacts dl{display:grid;grid-template-columns:90px 1fr;gap:10px 14px}.unitFacts dt{color:var(--muted)}.unitFacts dd{margin:0;font-weight:700}.existingContact{margin-top:16px;padding-top:16px;border-top:1px solid var(--line)}.proUnits .unitCard{position:relative;text-align:left;cursor:pointer;width:100%}.proUnits .unitCard>strong{position:absolute;right:16px;top:16px}.managementColumns{align-items:start}
@media(max-width:900px){.managementMetrics{grid-template-columns:repeat(2,1fr)}.unitDetailGrid,.formGrid.three{grid-template-columns:1fr}}@media(max-width:600px){.managementMetrics{grid-template-columns:1fr}.tenantCard{grid-template-columns:40px 1fr}.tenantCard>button{grid-column:2;text-align:left;padding:0}}
'''
css_p.write_text(css)
