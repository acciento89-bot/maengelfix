from pathlib import Path
import json, re

root = Path('.')

def replace(path, old, new, count=1):
    p=root/path; s=p.read_text()
    if old not in s: raise SystemExit(f'pattern not found in {path}: {old[:80]}')
    p.write_text(s.replace(old,new,count))

def append_once(path, marker, text):
    p=root/path; s=p.read_text()
    if marker not in s: p.write_text(s.rstrip()+"\n\n"+text.strip()+"\n")

# DB
append_once('server/schema.sql','-- v0.6: digitale Mieter-Verknüpfungen',r'''
-- v0.6: digitale Mieter-Verknüpfungen
ALTER TABLE properties ADD COLUMN IF NOT EXISTS allow_tenant_submissions boolean NOT NULL DEFAULT true;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS tenant_link_id text;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS submitted_by_tenant boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS tenant_invitations (
  id text PRIMARY KEY,
  token_hash text NOT NULL UNIQUE,
  organization_id text NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  property_id text NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  unit_id text NOT NULL REFERENCES units(id) ON DELETE CASCADE,
  contact_id text NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  email text NOT NULL,
  created_by text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at timestamptz NOT NULL,
  accepted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS tenant_invitations_email_idx ON tenant_invitations(lower(email), expires_at DESC);

CREATE TABLE IF NOT EXISTS tenant_links (
  id text PRIMARY KEY,
  organization_id text NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  property_id text NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  unit_id text NOT NULL REFERENCES units(id) ON DELETE CASCADE,
  contact_id text NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (unit_id, user_id)
);
CREATE INDEX IF NOT EXISTS tenant_links_user_idx ON tenant_links(user_id, status);
CREATE INDEX IF NOT EXISTS tenant_links_org_idx ON tenant_links(organization_id, status);

DO $$ BEGIN
  ALTER TABLE defect_cases ADD CONSTRAINT defect_cases_tenant_link_fk FOREIGN KEY (tenant_link_id) REFERENCES tenant_links(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
''')

# package + env
p=root/'server/package.json'; pkg=json.loads(p.read_text()); pkg['version']='0.6.0'; pkg['dependencies']['nodemailer']='^7.0.5'; p.write_text(json.dumps(pkg,indent=2,ensure_ascii=False)+"\n")
append_once('.env.example','SMTP_HOST=', '''SMTP_HOST=\nSMTP_PORT=587\nSMTP_SECURE=false\nSMTP_USER=\nSMTP_PASS=\nSMTP_FROM=MängelFix <noreply@kamilunavo.com>\n''')

# docker environment
replace('docker-compose.yml',"      UPLOAD_DIR: ${UPLOAD_DIR:-/data/uploads}\n", "      UPLOAD_DIR: ${UPLOAD_DIR:-/data/uploads}\n      SMTP_HOST: ${SMTP_HOST:-}\n      SMTP_PORT: ${SMTP_PORT:-587}\n      SMTP_SECURE: ${SMTP_SECURE:-false}\n      SMTP_USER: ${SMTP_USER:-}\n      SMTP_PASS: ${SMTP_PASS:-}\n      SMTP_FROM: ${SMTP_FROM:-MängelFix <noreply@kamilunavo.com>}\n")

# server imports/config
replace('server/index.js',"import pg from 'pg';\n", "import pg from 'pg';\nimport nodemailer from 'nodemailer';\n")
replace('server/index.js',"const production = process.env.NODE_ENV === 'production';\n", "const production = process.env.NODE_ENV === 'production';\nconst appOrigin = process.env.APP_ORIGIN || 'https://maengelfix.kamilunavo.com';\nconst smtpConfigured = Boolean(process.env.SMTP_HOST && process.env.SMTP_USER && process.env.SMTP_PASS);\nconst mailer = smtpConfigured ? nodemailer.createTransport({ host: process.env.SMTP_HOST, port: Number(process.env.SMTP_PORT || 587), secure: String(process.env.SMTP_SECURE || 'false') === 'true', auth: { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS } }) : null;\n")
replace('server/index.js',"  res.json({ ok: true, service: 'maengelfix', version: '0.5.0' });", "  res.json({ ok: true, service: 'maengelfix', version: '0.6.0', mail: smtpConfigured ? 'smtp' : 'manual' });")

# helper functions + invitation endpoints before management overview
anchor="app.get('/api/management/overview', auth, async (req, res, next) => {"
block=r'''
async function sendTenantInvitationMail({ to, tenantName, organizationName, propertyName, unitLabel, inviteUrl }) {
  if (!mailer) return false;
  await mailer.sendMail({
    from: process.env.SMTP_FROM || 'MängelFix <noreply@kamilunavo.com>',
    to,
    subject: `${organizationName} lädt dich zu MängelFix ein`,
    text: `Hallo ${tenantName || ''},\n\n${organizationName} möchte dein MängelFix-Privatkonto mit ${propertyName} – ${unitLabel} verknüpfen. Die Verknüpfung ist freiwillig. Deine privaten Vorgänge bleiben privat. Nur Mängel, die du ausdrücklich an die Hausverwaltung übermittelst, werden dort sichtbar.\n\nEinladung öffnen: ${inviteUrl}\n\nDer Link ist 7 Tage gültig.`,
    html: `<div style="font-family:Arial,sans-serif;max-width:620px;margin:auto;color:#18212b"><h2 style="margin-bottom:6px">MängelFix</h2><p><b>${organizationName}</b> möchte dein MängelFix-Privatkonto mit <b>${propertyName} – ${unitLabel}</b> verknüpfen.</p><p>Die Verknüpfung ist freiwillig. Deine privaten Vorgänge bleiben privat. Nur Mängel, die du ausdrücklich an die Hausverwaltung übermittelst, werden dort sichtbar.</p><p style="margin:28px 0"><a href="${inviteUrl}" style="background:#2457d6;color:white;text-decoration:none;padding:12px 18px;border-radius:6px">Einladung öffnen</a></p><p style="color:#6f7a86;font-size:13px">Der Link ist 7 Tage gültig.</p></div>`
  });
  return true;
}

app.post('/api/contacts/:contactId/invitations', auth, async (req, res, next) => {
  try {
    const organization = await organizationForUser(req.user.id);
    if (!organization || !['owner','admin'].includes(organization.role)) return res.status(403).json({ error: 'Nur Inhaber und Admins können Mieter einladen.' });
    const unitId = cleanText(req.body.unitId, 80);
    const row = await pool.query(`SELECT c.id AS contact_id,c.name,c.email,u.id AS unit_id,u.label AS unit_label,p.id AS property_id,p.name AS property_name,p.allow_tenant_submissions,o.name AS organization_name
      FROM contacts c JOIN unit_contacts uc ON uc.contact_id=c.id JOIN units u ON u.id=uc.unit_id JOIN properties p ON p.id=u.property_id JOIN organizations o ON o.id=p.organization_id
      WHERE c.id=$1 AND u.id=$2 AND p.organization_id=$3`, [req.params.contactId, unitId, organization.id]);
    if (!row.rowCount) return res.status(404).json({ error: 'Mieter oder Einheit nicht gefunden.' });
    const tenant=row.rows[0];
    if (!tenant.email) return res.status(400).json({ error: 'Für diesen Mieter ist keine E-Mail-Adresse hinterlegt.' });
    const active = await pool.query(`SELECT tl.id FROM tenant_links tl JOIN users usr ON usr.id=tl.user_id WHERE tl.unit_id=$1 AND lower(usr.email)=lower($2) AND tl.status='active'`, [unitId, tenant.email]);
    if (active.rowCount) return res.status(409).json({ error: 'Dieser Mieter ist bereits digital mit der Einheit verknüpft.' });
    await pool.query(`UPDATE tenant_invitations SET expires_at=now() WHERE contact_id=$1 AND unit_id=$2 AND accepted_at IS NULL AND expires_at>now()`, [tenant.contact_id, unitId]);
    const token=crypto.randomBytes(32).toString('base64url');
    const invitationId=id();
    await pool.query(`INSERT INTO tenant_invitations (id,token_hash,organization_id,property_id,unit_id,contact_id,email,created_by,expires_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,now()+interval '7 days')`, [invitationId,tokenHash(token),organization.id,tenant.property_id,unitId,tenant.contact_id,tenant.email.toLowerCase(),req.user.id]);
    const inviteUrl=`${appOrigin}/einladung/${token}`;
    let delivery='manual';
    try { if (await sendTenantInvitationMail({to:tenant.email,tenantName:tenant.name,organizationName:tenant.organization_name,propertyName:tenant.property_name,unitLabel:tenant.unit_label,inviteUrl})) delivery='email'; } catch (mailError) { console.error('Invitation mail failed', mailError); }
    res.status(201).json({ invitation: { id: invitationId, email: tenant.email, inviteUrl, delivery, expiresInDays: 7 } });
  } catch(error){ next(error); }
});

app.get('/api/invitations/:token', async (req,res,next)=>{
  try {
    const result=await pool.query(`SELECT ti.email,ti.expires_at,ti.accepted_at,o.name AS organization_name,p.name AS property_name,p.street,p.postal_code,p.city,u.label AS unit_label,c.name AS contact_name
      FROM tenant_invitations ti JOIN organizations o ON o.id=ti.organization_id JOIN properties p ON p.id=ti.property_id JOIN units u ON u.id=ti.unit_id JOIN contacts c ON c.id=ti.contact_id
      WHERE ti.token_hash=$1`, [tokenHash(req.params.token)]);
    if (!result.rowCount) return res.status(404).json({error:'Einladung nicht gefunden.'});
    const invitation=result.rows[0];
    if (invitation.accepted_at) return res.status(410).json({error:'Diese Einladung wurde bereits angenommen.'});
    if (new Date(invitation.expires_at)<=new Date()) return res.status(410).json({error:'Diese Einladung ist abgelaufen. Bitte fordere eine neue Einladung an.'});
    res.json({ invitation });
  } catch(error){ next(error); }
});

app.post('/api/invitations/:token/accept', auth, async (req,res,next)=>{
  const client=await pool.connect();
  try {
    await client.query('BEGIN');
    const result=await client.query(`SELECT ti.* FROM tenant_invitations ti WHERE ti.token_hash=$1 FOR UPDATE`, [tokenHash(req.params.token)]);
    if (!result.rowCount) { await client.query('ROLLBACK'); return res.status(404).json({error:'Einladung nicht gefunden.'}); }
    const inv=result.rows[0];
    if (inv.accepted_at || new Date(inv.expires_at)<=new Date()) { await client.query('ROLLBACK'); return res.status(410).json({error:'Diese Einladung ist nicht mehr gültig.'}); }
    if (String(req.user.email).toLowerCase() !== String(inv.email).toLowerCase()) { await client.query('ROLLBACK'); return res.status(403).json({error:`Diese Einladung wurde an ${inv.email} gesendet. Bitte melde dich mit genau dieser E-Mail-Adresse an.`}); }
    const linkId=id();
    const linked=await client.query(`INSERT INTO tenant_links (id,organization_id,property_id,unit_id,contact_id,user_id,status) VALUES ($1,$2,$3,$4,$5,$6,'active') ON CONFLICT (unit_id,user_id) DO UPDATE SET organization_id=EXCLUDED.organization_id,property_id=EXCLUDED.property_id,contact_id=EXCLUDED.contact_id,status='active' RETURNING *`, [linkId,inv.organization_id,inv.property_id,inv.unit_id,inv.contact_id,req.user.id]);
    await client.query(`UPDATE tenant_invitations SET accepted_at=now() WHERE id=$1`, [inv.id]);
    await client.query('COMMIT');
    res.json({ link: linked.rows[0] });
  } catch(error){ await client.query('ROLLBACK'); next(error); } finally { client.release(); }
});

app.get('/api/tenant-links', auth, async (req,res,next)=>{
  try {
    const result=await pool.query(`SELECT tl.id,tl.status,o.name AS organization_name,p.id AS property_id,p.name AS property_name,p.street,p.postal_code,p.city,p.allow_tenant_submissions,u.id AS unit_id,u.label AS unit_label,c.name AS contact_name
      FROM tenant_links tl JOIN organizations o ON o.id=tl.organization_id JOIN properties p ON p.id=tl.property_id JOIN units u ON u.id=tl.unit_id JOIN contacts c ON c.id=tl.contact_id
      WHERE tl.user_id=$1 AND tl.status='active' ORDER BY o.name,p.name,u.label`, [req.user.id]);
    res.json({ links: result.rows });
  } catch(error){ next(error); }
});

app.patch('/api/properties/:propertyId/tenant-submissions', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if (!organization || !['owner','admin'].includes(organization.role)) return res.status(403).json({error:'Nur Inhaber und Admins können diese Einstellung ändern.'});
    const result=await pool.query(`UPDATE properties SET allow_tenant_submissions=$3,updated_at=now() WHERE id=$1 AND organization_id=$2 RETURNING *`, [req.params.propertyId,organization.id,Boolean(req.body.enabled)]);
    if (!result.rowCount) return res.status(404).json({error:'Objekt nicht gefunden.'});
    res.json({property:result.rows[0]});
  } catch(error){next(error);}
});

'''
replace('server/index.js',anchor,block+anchor)

# enrich unit contact query with digital status
replace('server/index.js',"pool.query(`SELECT c.*,uc.role,uc.is_primary FROM unit_contacts uc JOIN contacts c ON c.id=uc.contact_id WHERE uc.unit_id=$1 ORDER BY uc.is_primary DESC,c.name`, [req.params.unitId]),", "pool.query(`SELECT c.*,uc.role,uc.is_primary, EXISTS(SELECT 1 FROM tenant_links tl WHERE tl.contact_id=c.id AND tl.unit_id=uc.unit_id AND tl.status='active') AS digitally_linked, (SELECT usr.email FROM tenant_links tl JOIN users usr ON usr.id=tl.user_id WHERE tl.contact_id=c.id AND tl.unit_id=uc.unit_id AND tl.status='active' LIMIT 1) AS linked_account_email FROM unit_contacts uc JOIN contacts c ON c.id=uc.contact_id WHERE uc.unit_id=$1 ORDER BY uc.is_primary DESC,c.name`, [req.params.unitId]),")

# tenant destination in case creation
old="""    const caseId = id();
    await client.query('BEGIN');
    const result = await client.query(
      `INSERT INTO defect_cases
       (id,user_id,organization_id,title,category,description,property_label,location_label,discovered_on,recipient_name,recipient_email,recipient_address,deadline_on,status)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,'draft')
       RETURNING *`,
      [
        caseId,
        req.user.id,
        (await organizationForUser(req.user.id))?.id || null,
        title,
"""
new="""    const caseId = id();
    await client.query('BEGIN');
    const ownOrganization = await organizationForUser(req.user.id);
    let destination = null;
    const destinationLinkId = cleanText(req.body.destinationLinkId, 80);
    if (destinationLinkId && !ownOrganization) {
      const destinationResult = await client.query(`SELECT tl.*,p.name AS property_name,p.street,p.postal_code,p.city,p.allow_tenant_submissions,u.label AS unit_label,o.name AS organization_name
        FROM tenant_links tl JOIN properties p ON p.id=tl.property_id JOIN units u ON u.id=tl.unit_id JOIN organizations o ON o.id=tl.organization_id
        WHERE tl.id=$1 AND tl.user_id=$2 AND tl.status='active'`, [destinationLinkId, req.user.id]);
      if (!destinationResult.rowCount) { await client.query('ROLLBACK'); return res.status(400).json({error:'Die ausgewählte Hausverwaltungs-Verknüpfung ist nicht gültig.'}); }
      destination=destinationResult.rows[0];
      if (!destination.allow_tenant_submissions) { await client.query('ROLLBACK'); return res.status(403).json({error:'Diese Hausverwaltung nimmt für dieses Objekt derzeit keine digitalen Mängelmeldungen über MängelFix an.'}); }
    }
    const organizationId = destination?.organization_id || ownOrganization?.id || null;
    const propertyLabel = destination ? [destination.property_name, destination.unit_label].filter(Boolean).join(' · ') : cleanText(req.body.propertyLabel, 200);
    const recipientName = destination?.organization_name || cleanText(req.body.recipientName, 160);
    const result = await client.query(
      `INSERT INTO defect_cases
       (id,user_id,organization_id,property_id,unit_id,tenant_link_id,submitted_by_tenant,title,category,description,property_label,location_label,discovered_on,recipient_name,recipient_email,recipient_address,deadline_on,status)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,'draft')
       RETURNING *`,
      [
        caseId,
        req.user.id,
        organizationId,
        destination?.property_id || null,
        destination?.unit_id || null,
        destination?.id || null,
        Boolean(destination),
        title,
"""
replace('server/index.js',old,new)
replace('server/index.js',"        cleanText(req.body.category, 80) || 'Sonstiges',\n        description,\n        cleanText(req.body.propertyLabel, 200),", "        cleanText(req.body.category, 80) || 'Sonstiges',\n        description,\n        propertyLabel,")
replace('server/index.js',"        cleanText(req.body.recipientName, 160),", "        recipientName,")
replace('server/index.js',"      [id(), caseId, req.user.id, 'created', 'Mangel wurde erfasst.']", "      [id(), caseId, req.user.id, 'created', destination ? `Mangel wurde vom Mieter digital an ${destination.organization_name} übermittelt.` : 'Mangel wurde erfasst.']")

# client: pending invite auth redirect
replace('client/src/App.jsx',"      onSignedIn(data.user);\n      navigate('/app');", "      onSignedIn(data.user);\n      const pendingInvite = window.localStorage.getItem('maengelfix_pending_invite');\n      navigate(pendingInvite ? `/einladung/${pendingInvite}` : '/app');")

# NewCase linked destinations
replace('client/src/App.jsx',"function NewCase({ onClose, onCreated }) {\n  const today", "function NewCase({ onClose, onCreated }) {\n  const [tenantLinks,setTenantLinks]=useState([]);\n  useEffect(()=>{ api('/api/tenant-links').then(d=>setTenantLinks(d.links||[])).catch(()=>setTenantLinks([])); },[]);\n  const today")
replace('client/src/App.jsx',"recipientAddress: '', deadlineOn: '' });", "recipientAddress: '', deadlineOn: '', destinationLinkId: '' });")
needle='''          <div className="subSection"><h3>Empfänger</h3><p className="muted">Optional – Hausverwaltung, Vermieter oder anderer Ansprechpartner.</p></div>'''
insert='''          {tenantLinks.length>0&&<div className="digitalDelivery"><div><span>DIGITALE ÜBERMITTLUNG</span><h3>Mit Hausverwaltung verknüpft</h3><p>Du entscheidest für jeden Mangel neu, ob er privat bleibt oder direkt an eine verknüpfte Verwaltung geht.</p></div><label>Übermittlung<select value={form.destinationLinkId} onChange={e=>field('destinationLinkId',e.target.value)}><option value="">Nur privat dokumentieren</option>{tenantLinks.filter(l=>l.allow_tenant_submissions).map(l=><option key={l.id} value={l.id}>An {l.organization_name} · {l.property_name} · {l.unit_label}</option>)}</select></label></div>}
          <div className="subSection"><h3>{form.destinationLinkId?'Zusätzlicher Empfänger (optional)':'Empfänger'}</h3><p className="muted">Optional – Hausverwaltung, Vermieter oder anderer Ansprechpartner.</p></div>'''
replace('client/src/App.jsx',needle,insert)

# invite action in ManagedObjects
replace('client/src/App.jsx',"  async function detachContact(contactId){try{await api(`/api/units/${unitDetail.unit.id}/contacts/${contactId}`,{method:'DELETE'});await loadUnit(unitDetail.unit.id);await loadProperty(propertyId)}catch(x){setError(x.message)}}", "  async function detachContact(contactId){try{await api(`/api/units/${unitDetail.unit.id}/contacts/${contactId}`,{method:'DELETE'});await loadUnit(unitDetail.unit.id);await loadProperty(propertyId)}catch(x){setError(x.message)}}\n  async function inviteTenant(contact){try{const d=await api(`/api/contacts/${contact.id}/invitations`,{method:'POST',body:JSON.stringify({unitId:unitDetail.unit.id})}); if(d.invitation.delivery==='email') alert(`Einladung wurde an ${d.invitation.email} gesendet.`); else { await navigator.clipboard?.writeText(d.invitation.inviteUrl); prompt('SMTP ist noch nicht eingerichtet. Einladung-Link wurde erzeugt – bitte kopieren und dem Mieter senden:',d.invitation.inviteUrl); } await loadUnit(unitDetail.unit.id);}catch(x){setError(x.message)}}")
oldcard="<button onClick={()=>detachContact(c.id)}>Entfernen</button></article>"
newcard="<div className=\"tenantActions\">{c.digitally_linked?<span className=\"linkedBadge\">DIGITAL VERKNÜPFT</span>:<button className=\"inviteTenantButton\" disabled={!c.email} onClick={()=>inviteTenant(c)}>{c.email?'Zu MängelFix einladen':'E-Mail fehlt'}</button>}<button onClick={()=>detachContact(c.id)}>Entfernen</button></div></article>"
replace('client/src/App.jsx',oldcard,newcard)

# property toggle in property detail heading
oldh="<div className=\"workspaceHeading\"><div><span>OBJEKT</span><h1>{detail.property.name}</h1><p>{[detail.property.street,[detail.property.postal_code,detail.property.city].filter(Boolean).join(' ')].filter(Boolean).join(' · ')}</p></div><button className=\"workspacePrimary\" onClick={()=>setShowUnit(true)}>+ Einheit anlegen</button></div>"
newh="<div className=\"workspaceHeading\"><div><span>OBJEKT</span><h1>{detail.property.name}</h1><p>{[detail.property.street,[detail.property.postal_code,detail.property.city].filter(Boolean).join(' ')].filter(Boolean).join(' · ')}</p></div><div className=\"propertyHeaderActions\"><label className=\"tenantSubmissionToggle\"><input type=\"checkbox\" checked={detail.property.allow_tenant_submissions!==false} onChange={async e=>{try{await api(`/api/properties/${propertyId}/tenant-submissions`,{method:'PATCH',body:JSON.stringify({enabled:e.target.checked})});await loadProperty(propertyId)}catch(x){setError(x.message)}}}/><span>Digitale Mietermeldungen</span></label><button className=\"workspacePrimary\" onClick={()=>setShowUnit(true)}>+ Einheit anlegen</button></div></div>"
replace('client/src/App.jsx',oldh,newh)

# Invitation page component before Workspace
anchor2="function Workspace({ user, setUser, onLogout, navigate }) {"
invcomp=r'''
function InvitationPage({ token, user, navigate }) {
  const [data,setData]=useState(null); const [error,setError]=useState(''); const [busy,setBusy]=useState(false); const [done,setDone]=useState(false);
  useEffect(()=>{window.localStorage.setItem('maengelfix_pending_invite',token);api(`/api/invitations/${token}`).then(setData).catch(e=>setError(e.message));},[token]);
  async function accept(){setBusy(true);setError('');try{await api(`/api/invitations/${token}/accept`,{method:'POST'});window.localStorage.removeItem('maengelfix_pending_invite');setDone(true);}catch(e){setError(e.message)}finally{setBusy(false)}}
  if(done)return <div className="invitationPage"><PublicHeader user={user} navigate={navigate}/><main className="invitationCard successInvitation"><Logo/><span>VERKNÜPFUNG AKTIV</span><h1>Deine Wohnung ist verbunden.</h1><p>Bei jedem neuen Mangel kannst du nun selbst entscheiden, ob er privat bleibt oder direkt an die Hausverwaltung übermittelt wird.</p><button className="primaryButton" onClick={()=>navigate('/app')}>MängelFix öffnen →</button></main><PublicFooter navigate={navigate}/></div>;
  return <div className="invitationPage"><PublicHeader user={user} navigate={navigate}/><main className="invitationCard"><Logo/><span>MIETER-EINLADUNG</span>{error?<div className="errorBox">{error}</div>:!data?<p>Einladung wird geladen…</p>:<><h1>{data.invitation.organization_name} möchte sich mit dir verbinden.</h1><div className="invitationFacts"><div><small>Objekt</small><b>{data.invitation.property_name}</b><span>{[data.invitation.street,[data.invitation.postal_code,data.invitation.city].filter(Boolean).join(' ')].filter(Boolean).join(', ')}</span></div><div><small>Einheit</small><b>{data.invitation.unit_label}</b></div></div><div className="privacyPromise"><b>Deine privaten Vorgänge bleiben privat.</b><p>Die Hausverwaltung sieht nur Mängel, die du später ausdrücklich an sie übermittelst. Die Verknüpfung allein gibt keinen Zugriff auf deine übrigen Inhalte.</p></div>{user?<><p>Angemeldet als <b>{user.email}</b>.</p><button className="primaryButton" disabled={busy} onClick={accept}>{busy?'Verknüpfen…':'Verknüpfung akzeptieren'}</button></>:<div className="inviteAuth"><p>Bitte registriere dich mit <b>{data.invitation.email}</b> oder melde dich mit einem bestehenden Konto unter dieser E-Mail-Adresse an.</p><button className="primaryButton" onClick={()=>navigate('/registrieren')}>Privatkonto erstellen</button><button className="secondaryButton" onClick={()=>navigate('/anmelden')}>Anmelden</button></div>}</>}</main><PublicFooter navigate={navigate}/></div>;
}

'''
replace('client/src/App.jsx',anchor2,invcomp+anchor2)

# app routing invite
replace('client/src/App.jsx',"  if (path === '/nutzungsbedingungen') return <LegalPage type=\"terms\" navigate={navigate} />;", "  if (path === '/nutzungsbedingungen') return <LegalPage type=\"terms\" navigate={navigate} />;\n  if (path.startsWith('/einladung/')) return <InvitationPage token={path.split('/').pop()} user={state.user} navigate={navigate} />;")

# css additions
append_once('client/src/maengelfix-pro.css','/* v0.6 tenant connection */',r'''
/* v0.6 tenant connection */
.digitalDelivery{border:1px solid #bed0ff;background:#f3f6ff;padding:18px;display:grid;grid-template-columns:1.4fr 1fr;gap:18px;margin:8px 0 18px}.digitalDelivery span{font-size:11px;font-weight:800;letter-spacing:.12em;color:#2457d6}.digitalDelivery h3{margin:5px 0}.digitalDelivery p{margin:0;color:#65717d}.digitalDelivery label{align-self:center}.tenantActions{display:flex;align-items:center;gap:8px;margin-left:auto}.inviteTenantButton{border:1px solid #2457d6;color:#2457d6;background:#fff;padding:8px 10px;font-weight:700;cursor:pointer}.linkedBadge{font-size:10px;font-weight:800;color:#19764b;background:#e8f8ef;padding:7px 9px;border-radius:3px}.propertyHeaderActions{display:flex;align-items:center;gap:14px}.tenantSubmissionToggle{display:flex!important;flex-direction:row!important;align-items:center;gap:8px;font-weight:700;font-size:13px}.tenantSubmissionToggle input{width:auto}.invitationPage{min-height:100vh;background:#f3f5f7}.invitationCard{max-width:720px;margin:70px auto;padding:42px;background:white;border-top:5px solid #2457d6;box-shadow:0 16px 50px rgba(24,33,43,.1)}.invitationCard>span{display:block;margin-top:30px;color:#2457d6;font-size:11px;font-weight:900;letter-spacing:.13em}.invitationCard h1{font-size:34px;line-height:1.1;margin:10px 0 24px}.invitationFacts{display:grid;grid-template-columns:2fr 1fr;gap:12px;margin:22px 0}.invitationFacts>div{background:#f4f6f8;padding:16px}.invitationFacts small,.invitationFacts span{display:block;color:#6f7a86}.privacyPromise{border-left:4px solid #e4a11b;background:#fff9ec;padding:16px 18px;margin:24px 0}.privacyPromise p{margin:6px 0 0;color:#65717d}.inviteAuth{display:flex;gap:10px;flex-wrap:wrap}.inviteAuth p{width:100%}.successInvitation{border-top-color:#2c9b64}@media(max-width:760px){.digitalDelivery{grid-template-columns:1fr}.propertyHeaderActions{align-items:flex-start;flex-direction:column}.invitationCard{margin:20px 12px;padding:24px}.invitationFacts{grid-template-columns:1fr}.tenantActions{flex-direction:column;align-items:flex-end}}
''')

print('v0.6 patch applied')
