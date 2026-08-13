from pathlib import Path

root = Path('.')
schema_path = root / 'server/schema.sql'
server_path = root / 'server/index.js'
app_path = root / 'client/src/App.jsx'
css_path = root / 'client/src/maengelfix-pro.css'

schema = schema_path.read_text()
server = server_path.read_text()
app = app_path.read_text()
css = css_path.read_text()

schema_append = r'''

-- v0.4: echte Objekt-/Einheitenstruktur für Hausverwaltungen
CREATE TABLE IF NOT EXISTS properties (
  id text PRIMARY KEY,
  organization_id text REFERENCES organizations(id) ON DELETE CASCADE,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name text NOT NULL,
  street text,
  postal_code text,
  city text,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS properties_org_idx ON properties(organization_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS properties_user_idx ON properties(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS units (
  id text PRIMARY KEY,
  property_id text NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  label text NOT NULL,
  floor text,
  position_label text,
  area_sqm numeric,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS units_property_idx ON units(property_id, label);

CREATE TABLE IF NOT EXISTS contacts (
  id text PRIMARY KEY,
  organization_id text REFERENCES organizations(id) ON DELETE CASCADE,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name text NOT NULL,
  email text,
  phone text,
  contact_type text NOT NULL DEFAULT 'tenant',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS contacts_org_idx ON contacts(organization_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS contacts_user_idx ON contacts(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS unit_contacts (
  unit_id text NOT NULL REFERENCES units(id) ON DELETE CASCADE,
  contact_id text NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  role text NOT NULL DEFAULT 'tenant',
  is_primary boolean NOT NULL DEFAULT false,
  PRIMARY KEY (unit_id, contact_id)
);

ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS property_id text REFERENCES properties(id) ON DELETE SET NULL;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS unit_id text REFERENCES units(id) ON DELETE SET NULL;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS assigned_user_id text REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS defect_cases_property_idx ON defect_cases(property_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS defect_cases_unit_idx ON defect_cases(unit_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS defect_cases_assignee_idx ON defect_cases(assigned_user_id, updated_at DESC);
'''
if '-- v0.4:' not in schema:
    schema += schema_append
schema_path.write_text(schema)

server = server.replace("version: '0.3.0'", "version: '0.4.0'")

marker = "app.get('/api/cases', auth, async (req, res, next) => {"
api_block = r'''

async function scopeForUser(userId) {
  const organization = await organizationForUser(userId);
  return { organization, organizationId: organization?.id || null };
}

app.get('/api/properties', auth, async (req, res, next) => {
  try {
    const { organizationId } = await scopeForUser(req.user.id);
    const result = await pool.query(
      `SELECT p.*,
        (SELECT count(*)::int FROM units u WHERE u.property_id=p.id) AS unit_count,
        (SELECT count(*)::int FROM defect_cases c WHERE c.property_id=p.id AND c.status <> 'resolved') AS open_case_count
       FROM properties p
       WHERE ($2::text IS NOT NULL AND p.organization_id=$2) OR ($2::text IS NULL AND p.organization_id IS NULL AND p.user_id=$1)
       ORDER BY p.name`,
      [req.user.id, organizationId]
    );
    res.json({ properties: result.rows });
  } catch (error) { next(error); }
});

app.post('/api/properties', auth, async (req, res, next) => {
  try {
    const name = cleanText(req.body.name, 180);
    if (!name) return res.status(400).json({ error: 'Bitte gib einen Objektnamen an.' });
    const { organizationId } = await scopeForUser(req.user.id);
    const propertyId = id();
    const result = await pool.query(
      `INSERT INTO properties (id,organization_id,user_id,name,street,postal_code,city,notes)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *`,
      [propertyId, organizationId, req.user.id, name, cleanText(req.body.street,180), cleanText(req.body.postalCode,20), cleanText(req.body.city,120), cleanText(req.body.notes,2000)]
    );
    res.status(201).json({ property: result.rows[0] });
  } catch (error) { next(error); }
});

app.get('/api/properties/:propertyId', auth, async (req, res, next) => {
  try {
    const { organizationId } = await scopeForUser(req.user.id);
    const property = await pool.query(
      `SELECT * FROM properties WHERE id=$1 AND (($3::text IS NOT NULL AND organization_id=$3) OR ($3::text IS NULL AND organization_id IS NULL AND user_id=$2))`,
      [req.params.propertyId, req.user.id, organizationId]
    );
    if (!property.rowCount) return res.status(404).json({ error: 'Objekt nicht gefunden.' });
    const [units, cases] = await Promise.all([
      pool.query(`SELECT u.*,
          (SELECT count(*)::int FROM unit_contacts uc WHERE uc.unit_id=u.id) AS contact_count,
          (SELECT count(*)::int FROM defect_cases c WHERE c.unit_id=u.id AND c.status <> 'resolved') AS open_case_count
        FROM units u WHERE u.property_id=$1 ORDER BY u.label`, [req.params.propertyId]),
      pool.query(`SELECT c.*, u.name AS assigned_user_name FROM defect_cases c LEFT JOIN users u ON u.id=c.assigned_user_id WHERE c.property_id=$1 ORDER BY c.updated_at DESC`, [req.params.propertyId])
    ]);
    res.json({ property: property.rows[0], units: units.rows, cases: cases.rows });
  } catch (error) { next(error); }
});

app.post('/api/properties/:propertyId/units', auth, async (req, res, next) => {
  try {
    const { organizationId } = await scopeForUser(req.user.id);
    const property = await pool.query(`SELECT 1 FROM properties WHERE id=$1 AND (($3::text IS NOT NULL AND organization_id=$3) OR ($3::text IS NULL AND organization_id IS NULL AND user_id=$2))`, [req.params.propertyId, req.user.id, organizationId]);
    if (!property.rowCount) return res.status(404).json({ error: 'Objekt nicht gefunden.' });
    const label = cleanText(req.body.label,120);
    if (!label) return res.status(400).json({ error: 'Bitte gib eine Bezeichnung für die Einheit an.' });
    const result = await pool.query(
      `INSERT INTO units (id,property_id,label,floor,position_label,area_sqm) VALUES ($1,$2,$3,$4,$5,$6) RETURNING *`,
      [id(), req.params.propertyId, label, cleanText(req.body.floor,60), cleanText(req.body.positionLabel,120), req.body.areaSqm ? Number(req.body.areaSqm) : null]
    );
    res.status(201).json({ unit: result.rows[0] });
  } catch (error) { next(error); }
});

app.get('/api/contacts', auth, async (req, res, next) => {
  try {
    const { organizationId } = await scopeForUser(req.user.id);
    const result = await pool.query(
      `SELECT * FROM contacts WHERE ($2::text IS NOT NULL AND organization_id=$2) OR ($2::text IS NULL AND organization_id IS NULL AND user_id=$1) ORDER BY name`,
      [req.user.id, organizationId]
    );
    res.json({ contacts: result.rows });
  } catch (error) { next(error); }
});

app.post('/api/contacts', auth, async (req, res, next) => {
  try {
    const name = cleanText(req.body.name,160);
    if (!name) return res.status(400).json({ error: 'Bitte gib einen Namen an.' });
    const { organizationId } = await scopeForUser(req.user.id);
    const result = await pool.query(
      `INSERT INTO contacts (id,organization_id,user_id,name,email,phone,contact_type) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *`,
      [id(), organizationId, req.user.id, name, cleanText(req.body.email,254)?.toLowerCase(), cleanText(req.body.phone,60), cleanText(req.body.contactType,40) || 'tenant']
    );
    res.status(201).json({ contact: result.rows[0] });
  } catch (error) { next(error); }
});

app.post('/api/units/:unitId/contacts', auth, async (req, res, next) => {
  try {
    const { organizationId } = await scopeForUser(req.user.id);
    const unit = await pool.query(`SELECT u.id FROM units u JOIN properties p ON p.id=u.property_id WHERE u.id=$1 AND (($3::text IS NOT NULL AND p.organization_id=$3) OR ($3::text IS NULL AND p.organization_id IS NULL AND p.user_id=$2))`, [req.params.unitId, req.user.id, organizationId]);
    if (!unit.rowCount) return res.status(404).json({ error: 'Einheit nicht gefunden.' });
    const contact = await pool.query(`SELECT id FROM contacts WHERE id=$1 AND (($3::text IS NOT NULL AND organization_id=$3) OR ($3::text IS NULL AND organization_id IS NULL AND user_id=$2))`, [req.body.contactId, req.user.id, organizationId]);
    if (!contact.rowCount) return res.status(404).json({ error: 'Kontakt nicht gefunden.' });
    await pool.query(`INSERT INTO unit_contacts (unit_id,contact_id,role,is_primary) VALUES ($1,$2,$3,$4) ON CONFLICT (unit_id,contact_id) DO UPDATE SET role=EXCLUDED.role,is_primary=EXCLUDED.is_primary`, [req.params.unitId, req.body.contactId, cleanText(req.body.role,40) || 'tenant', Boolean(req.body.isPrimary)]);
    res.status(204).end();
  } catch (error) { next(error); }
});

app.patch('/api/cases/:caseId/assignment', auth, async (req, res, next) => {
  try {
    const accessible = await canAccessCase(req.user.id, req.params.caseId);
    if (!accessible) return res.status(404).json({ error: 'Mangel nicht gefunden.' });
    const propertyId = cleanText(req.body.propertyId,80) || null;
    const unitId = cleanText(req.body.unitId,80) || null;
    const assignedUserId = cleanText(req.body.assignedUserId,80) || null;
    const result = await pool.query(`UPDATE defect_cases SET property_id=$2, unit_id=$3, assigned_user_id=$4, updated_at=now() WHERE id=$1 RETURNING *`, [req.params.caseId, propertyId, unitId, assignedUserId]);
    res.json({ case: result.rows[0] });
  } catch (error) { next(error); }
});
'''
if "app.get('/api/properties'" not in server:
    server = server.replace(marker, api_block + '\n' + marker)
server_path.write_text(server)

# Add UI data loading and object management components.
insert_before = "function DeadlinesView({ cases, onSelect }) {"
ui_block = r'''

function ManagedObjectsView({ onSelect }) {
  const [properties, setProperties] = useState([]);
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [detail, setDetail] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [showUnit, setShowUnit] = useState(false);
  const [form, setForm] = useState({ name:'', street:'', postalCode:'', city:'', notes:'' });
  const [unitForm, setUnitForm] = useState({ label:'', floor:'', positionLabel:'', areaSqm:'' });
  const [error, setError] = useState('');

  async function loadProperties() { try { const data=await api('/api/properties'); setProperties(data.properties); } catch(err){ setError(err.message); } }
  async function loadDetail(id) { try { const data=await api(`/api/properties/${id}`); setDetail(data); setSelectedProperty(id); } catch(err){ setError(err.message); } }
  useEffect(()=>{ loadProperties(); },[]);

  async function createProperty(e){ e.preventDefault(); try { const data=await api('/api/properties',{method:'POST',body:JSON.stringify(form)}); setShowNew(false); setForm({name:'',street:'',postalCode:'',city:'',notes:''}); await loadProperties(); await loadDetail(data.property.id); } catch(err){ setError(err.message); } }
  async function createUnit(e){ e.preventDefault(); try { await api(`/api/properties/${selectedProperty}/units`,{method:'POST',body:JSON.stringify(unitForm)}); setShowUnit(false); setUnitForm({label:'',floor:'',positionLabel:'',areaSqm:''}); await loadDetail(selectedProperty); await loadProperties(); } catch(err){ setError(err.message); } }

  if (selectedProperty && detail) return <div className="workspacePage"><button className="backButton" onClick={()=>{setSelectedProperty(null);setDetail(null);}}>← Alle Objekte</button><div className="workspaceHeading"><div><span>OBJEKT</span><h1>{detail.property.name}</h1><p>{[detail.property.street,[detail.property.postal_code,detail.property.city].filter(Boolean).join(' ')].filter(Boolean).join(' · ')}</p></div><button className="workspacePrimary" onClick={()=>setShowUnit(true)}>+ Einheit anlegen</button></div><div className="metricGrid"><div><span>EINHEITEN</span><strong>{detail.units.length}</strong><small>Wohnungen / Gewerbe</small></div><div><span>VORGÄNGE</span><strong>{detail.cases.length}</strong><small>diesem Objekt zugeordnet</small></div><div><span>OFFEN</span><strong>{detail.cases.filter(x=>x.status!=='resolved').length}</strong><small>brauchen Aufmerksamkeit</small></div></div><section className="workspacePanel"><div className="panelHead"><div><span>EINHEITEN</span><h2>Wohnungen & Bereiche</h2></div></div><div className="unitGrid">{detail.units.length ? detail.units.map(u=><article className="unitCard" key={u.id}><span>EINHEIT</span><h3>{u.label}</h3><p>{[u.floor,u.position_label].filter(Boolean).join(' · ') || 'Keine Zusatzangaben'}</p><div><b>{u.open_case_count}</b> offene Vorgänge · <b>{u.contact_count}</b> Kontakte</div></article>) : <div className="emptyCard workspaceEmpty">Noch keine Einheiten angelegt.</div>}</div></section><section className="workspacePanel"><div className="panelHead"><div><span>VORGÄNGE</span><h2>Mängel am Objekt</h2></div></div><CaseRows cases={detail.cases} onSelect={onSelect} emptyText="Noch keine Mängel diesem Objekt zugeordnet." /></section>{showUnit&&<div className="modalBackdrop" onMouseDown={()=>setShowUnit(false)}><div className="modal proModal" onMouseDown={e=>e.stopPropagation()}><div className="modalHeader"><div><div className="eyebrow">NEUE EINHEIT</div><h2>Wohnung / Einheit anlegen</h2></div><button className="iconButton" onClick={()=>setShowUnit(false)}>×</button></div><form className="caseForm" onSubmit={createUnit}><label>Bezeichnung<input required placeholder="z. B. EG links / WE 01" value={unitForm.label} onChange={e=>setUnitForm({...unitForm,label:e.target.value})}/></label><div className="formGrid two"><label>Etage<input value={unitForm.floor} onChange={e=>setUnitForm({...unitForm,floor:e.target.value})}/></label><label>Lage<input placeholder="links / rechts / Mitte" value={unitForm.positionLabel} onChange={e=>setUnitForm({...unitForm,positionLabel:e.target.value})}/></label><label>Fläche m²<input type="number" step="0.1" value={unitForm.areaSqm} onChange={e=>setUnitForm({...unitForm,areaSqm:e.target.value})}/></label></div><div className="modalActions"><button type="button" className="secondaryButton" onClick={()=>setShowUnit(false)}>Abbrechen</button><button className="primaryButton">Einheit speichern</button></div></form></div></div>}</div>;

  return <div className="workspacePage"><div className="workspaceHeading"><div><span>OBJEKTE</span><h1>Gebäude & Liegenschaften</h1><p>Objekte verwalten, Einheiten strukturieren und Mängel sauber zuordnen.</p></div><button className="workspacePrimary" onClick={()=>setShowNew(true)}>+ Objekt anlegen</button></div>{error&&<div className="errorBox">{error}</div>}<div className="managedObjectGrid">{properties.length ? properties.map(p=><button className="managedObjectCard" key={p.id} onClick={()=>loadDetail(p.id)}><div className="managedObjectIcon">⌂</div><div><span>OBJEKT</span><h2>{p.name}</h2><p>{[p.street,[p.postal_code,p.city].filter(Boolean).join(' ')].filter(Boolean).join(' · ') || 'Keine Adresse hinterlegt'}</p></div><div className="managedObjectStats"><span><b>{p.unit_count}</b> Einheiten</span><span><b>{p.open_case_count}</b> offen</span></div><strong>→</strong></button>) : <div className="emptyCard workspaceEmpty">Noch kein Objekt angelegt.</div>}</div>{showNew&&<div className="modalBackdrop" onMouseDown={()=>setShowNew(false)}><div className="modal proModal" onMouseDown={e=>e.stopPropagation()}><div className="modalHeader"><div><div className="eyebrow">NEUES OBJEKT</div><h2>Gebäude anlegen</h2></div><button className="iconButton" onClick={()=>setShowNew(false)}>×</button></div><form className="caseForm" onSubmit={createProperty}><label>Objektname<input required placeholder="z. B. Musterstraße 12" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label><label>Straße & Hausnummer<input value={form.street} onChange={e=>setForm({...form,street:e.target.value})}/></label><div className="formGrid two"><label>PLZ<input value={form.postalCode} onChange={e=>setForm({...form,postalCode:e.target.value})}/></label><label>Ort<input value={form.city} onChange={e=>setForm({...form,city:e.target.value})}/></label></div><label>Interne Notiz<textarea rows="3" value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></label><div className="modalActions"><button type="button" className="secondaryButton" onClick={()=>setShowNew(false)}>Abbrechen</button><button className="primaryButton">Objekt speichern</button></div></form></div></div>}</div>;
}
'''
if 'function ManagedObjectsView' not in app:
    app = app.replace(insert_before, ui_block + '\n' + insert_before)

app = app.replace("else if (view === 'objects') content = <ObjectsView cases={cases} onSelect={setSelected} />;", "else if (view === 'objects') content = <ManagedObjectsView onSelect={setSelected} />;")
app_path.write_text(app)

css_append = r'''

/* v0.4 Objektverwaltung */
.managedObjectGrid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; }
.managedObjectCard { display:grid; grid-template-columns:52px 1fr auto 22px; gap:16px; align-items:center; text-align:left; border:1px solid var(--line); background:var(--surface); border-radius:10px; padding:20px; color:var(--text); box-shadow:0 4px 16px rgba(26,36,48,.035); }
.managedObjectCard:hover { border-color:var(--primary); box-shadow:inset 4px 0 0 var(--primary); }
.managedObjectIcon { width:44px; height:44px; display:grid; place-items:center; background:var(--primary-soft); color:var(--primary); border-radius:8px; font-size:22px; }
.managedObjectCard span,.unitCard>span { font-size:9px; letter-spacing:.08em; color:var(--muted); }
.managedObjectCard h2 { margin:4px 0; font-size:18px; }
.managedObjectCard p { margin:0; color:var(--muted); font-size:13px; }
.managedObjectStats { display:flex; gap:14px; color:var(--muted); font-size:12px; }
.managedObjectStats span { letter-spacing:0; font-size:12px; }
.managedObjectStats b { color:var(--text); font-size:15px; margin-right:3px; }
.unitGrid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; padding-top:8px; }
.unitCard { border:1px solid var(--line); background:var(--surface-2); border-radius:8px; padding:16px; }
.unitCard h3 { margin:5px 0 4px; text-transform:none; letter-spacing:0; color:var(--text); }
.unitCard p { color:var(--muted); margin:0 0 14px; }
.unitCard div { color:var(--muted); font-size:12px; }
@media(max-width:720px){ .managedObjectCard{grid-template-columns:44px 1fr 20px}.managedObjectStats{grid-column:2 / -1}.managedObjectGrid{grid-template-columns:1fr} }
'''
if 'v0.4 Objektverwaltung' not in css:
    css += css_append
css_path.write_text(css)
