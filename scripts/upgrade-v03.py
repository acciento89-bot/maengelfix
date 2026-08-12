from pathlib import Path


def replace_once(text, old, new, label):
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f'Marker not found: {label}')
    return text.replace(old, new, 1)

# --- Database / team model -------------------------------------------------
schema_path = Path('server/schema.sql')
schema = schema_path.read_text()
team_schema = r'''

-- v0.3: Privat- und Hausverwaltungs-Arbeitsbereiche
CREATE TABLE IF NOT EXISTS organizations (
  id text PRIMARY KEY,
  name text NOT NULL,
  plan_code text NOT NULL DEFAULT 'business',
  created_by text NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organization_memberships (
  organization_id text NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role text NOT NULL DEFAULT 'member',
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, user_id)
);
CREATE INDEX IF NOT EXISTS organization_memberships_user_idx ON organization_memberships(user_id);

ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS organization_id text REFERENCES organizations(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS defect_cases_org_idx ON defect_cases(organization_id, updated_at DESC);
'''
if '-- v0.3: Privat- und Hausverwaltungs-Arbeitsbereiche' not in schema:
    schema += team_schema
    schema_path.write_text(schema)

# --- Server ----------------------------------------------------------------
server_path = Path('server/index.js')
server = server_path.read_text()
server = server.replace("version: '0.2.0'", "version: '0.3.0'")

helper_marker = "const allowedStatuses = new Set(['draft', 'sent', 'reply', 'in_progress', 'resolved']);\n"
helpers = helper_marker + r'''

async function organizationForUser(userId) {
  const result = await pool.query(
    `SELECT o.id, o.name, o.plan_code, om.role
     FROM organization_memberships om
     JOIN organizations o ON o.id = om.organization_id
     WHERE om.user_id = $1
     ORDER BY om.created_at
     LIMIT 1`,
    [userId]
  );
  return result.rows[0] || null;
}

async function canAccessCase(userId, caseId) {
  const result = await pool.query(
    `SELECT c.*
     FROM defect_cases c
     WHERE c.id = $1 AND (
       c.user_id = $2 OR
       (c.organization_id IS NOT NULL AND EXISTS (
         SELECT 1 FROM organization_memberships om
         WHERE om.organization_id = c.organization_id AND om.user_id = $2
       ))
     )`,
    [caseId, userId]
  );
  return result.rows[0] || null;
}
'''
server = replace_once(server, helper_marker, helpers, 'server helpers')

profile_endpoint_end = "app.get('/api/cases', auth, async (req, res, next) => {"
team_endpoints = r'''
app.get('/api/team', auth, async (req, res, next) => {
  try {
    const organization = await organizationForUser(req.user.id);
    if (!organization) return res.json({ organization: null, members: [] });
    const members = await pool.query(
      `SELECT u.id, u.name, u.email, om.role, om.created_at
       FROM organization_memberships om
       JOIN users u ON u.id = om.user_id
       WHERE om.organization_id = $1
       ORDER BY CASE om.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, u.name`,
      [organization.id]
    );
    res.json({ organization, members: members.rows });
  } catch (error) {
    next(error);
  }
});

app.post('/api/team', auth, async (req, res, next) => {
  try {
    const existing = await organizationForUser(req.user.id);
    if (existing) return res.status(409).json({ error: 'Du gehörst bereits zu einem Hausverwaltungs-Arbeitsbereich.' });
    const name = cleanText(req.body.name, 180);
    if (!name) return res.status(400).json({ error: 'Bitte gib den Namen der Hausverwaltung an.' });
    const orgId = id();
    await pool.query('BEGIN');
    try {
      await pool.query(
        `INSERT INTO organizations (id, name, plan_code, created_by) VALUES ($1,$2,'business',$3)`,
        [orgId, name, req.user.id]
      );
      await pool.query(
        `INSERT INTO organization_memberships (organization_id, user_id, role) VALUES ($1,$2,'owner')`,
        [orgId, req.user.id]
      );
      await pool.query('COMMIT');
    } catch (error) {
      await pool.query('ROLLBACK');
      throw error;
    }
    res.status(201).json({ organization: { id: orgId, name, plan_code: 'business', role: 'owner' } });
  } catch (error) {
    next(error);
  }
});

app.post('/api/team/members', auth, async (req, res, next) => {
  try {
    const organization = await organizationForUser(req.user.id);
    if (!organization || !['owner', 'admin'].includes(organization.role)) {
      return res.status(403).json({ error: 'Nur Inhaber und Admins können Mitarbeiterkonten anlegen.' });
    }
    const name = cleanText(req.body.name, 120);
    const email = cleanText(req.body.email, 254)?.toLowerCase();
    const password = String(req.body.password || '');
    const role = req.body.role === 'admin' ? 'admin' : 'member';
    if (!name || !email || !email.includes('@') || password.length < 8) {
      return res.status(400).json({ error: 'Name, gültige E-Mail und ein Startpasswort mit mindestens 8 Zeichen sind erforderlich.' });
    }
    const existing = await pool.query('SELECT id FROM users WHERE email=$1', [email]);
    if (existing.rowCount) return res.status(409).json({ error: 'Für diese E-Mail existiert bereits ein MängelFix-Konto.' });
    const credentials = await makePassword(password);
    const userId = id();
    await pool.query('BEGIN');
    try {
      await pool.query(
        `INSERT INTO users (id,name,email,password_salt,password_hash,country) VALUES ($1,$2,$3,$4,$5,'Deutschland')`,
        [userId, name, email, credentials.salt, credentials.hash]
      );
      await pool.query(
        `INSERT INTO organization_memberships (organization_id,user_id,role) VALUES ($1,$2,$3)`,
        [organization.id, userId, role]
      );
      await pool.query('COMMIT');
    } catch (error) {
      await pool.query('ROLLBACK');
      throw error;
    }
    res.status(201).json({ member: { id: userId, name, email, role } });
  } catch (error) {
    next(error);
  }
});

'''
if "app.get('/api/team'" not in server:
    server = replace_once(server, profile_endpoint_end, team_endpoints + profile_endpoint_end, 'team endpoints')

old_cases_list = r'''      `SELECT c.*,
        (SELECT count(*)::int FROM attachments a WHERE a.case_id = c.id) AS attachment_count
       FROM defect_cases c
       WHERE c.user_id = $1
       ORDER BY c.updated_at DESC`,
      [req.user.id]'''
new_cases_list = r'''      `SELECT c.*,
        (SELECT count(*)::int FROM attachments a WHERE a.case_id = c.id) AS attachment_count
       FROM defect_cases c
       WHERE c.user_id = $1 OR (
         c.organization_id IS NOT NULL AND EXISTS (
           SELECT 1 FROM organization_memberships om
           WHERE om.organization_id = c.organization_id AND om.user_id = $1
         )
       )
       ORDER BY c.updated_at DESC`,
      [req.user.id]'''
server = replace_once(server, old_cases_list, new_cases_list, 'case list access')

old_insert = """      `INSERT INTO defect_cases\n       (id,user_id,title,category,description,property_label,location_label,discovered_on,recipient_name,recipient_email,recipient_address,deadline_on,status)\n       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,'draft')\n       RETURNING *`,\n      [\n        caseId,\n        req.user.id,\n        title,"""
new_insert = """      `INSERT INTO defect_cases\n       (id,user_id,organization_id,title,category,description,property_label,location_label,discovered_on,recipient_name,recipient_email,recipient_address,deadline_on,status)\n       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,'draft')\n       RETURNING *`,\n      [\n        caseId,\n        req.user.id,\n        (await organizationForUser(req.user.id))?.id || null,\n        title,"""
server = replace_once(server, old_insert, new_insert, 'case insert org')

# Parameter positions after adding organization_id shift by one.
server = server.replace("cleanText(req.body.category, 80) || 'Sonstiges',\n        description,", "cleanText(req.body.category, 80) || 'Sonstiges',\n        description,", 1)
# SQL already accepts the array in order; values count is correct after inserted org because title and following values remain sequential.

server = replace_once(
    server,
    "const result = await pool.query('SELECT * FROM defect_cases WHERE id = $1 AND user_id = $2', [req.params.caseId, req.user.id]);",
    "const accessible = await canAccessCase(req.user.id, req.params.caseId);\n    const result = { rowCount: accessible ? 1 : 0, rows: accessible ? [accessible] : [] };",
    'case detail access'
)
server = replace_once(
    server,
    "pool.query('SELECT * FROM case_events WHERE case_id = $1 AND user_id = $2 ORDER BY created_at DESC', [req.params.caseId, req.user.id]),\n      pool.query('SELECT id, original_name, mime_type, size_bytes, created_at FROM attachments WHERE case_id = $1 AND user_id = $2 ORDER BY created_at', [req.params.caseId, req.user.id])",
    "pool.query('SELECT e.*, u.name AS actor_name FROM case_events e LEFT JOIN users u ON u.id=e.user_id WHERE e.case_id = $1 ORDER BY e.created_at DESC', [req.params.caseId]),\n      pool.query('SELECT id, original_name, mime_type, size_bytes, created_at FROM attachments WHERE case_id = $1 ORDER BY created_at', [req.params.caseId])",
    'case related access'
)
server = replace_once(
    server,
    "const current = await pool.query('SELECT * FROM defect_cases WHERE id=$1 AND user_id=$2', [req.params.caseId, req.user.id]);",
    "const accessible = await canAccessCase(req.user.id, req.params.caseId);\n    const current = { rowCount: accessible ? 1 : 0, rows: accessible ? [accessible] : [] };",
    'case patch access'
)
server = server.replace("WHERE id=$1 AND user_id=$2 RETURNING *`,", "WHERE id=$1 RETURNING *`,", 1)
server = replace_once(
    server,
    "const owner = await pool.query('SELECT 1 FROM defect_cases WHERE id=$1 AND user_id=$2', [req.params.caseId, req.user.id]);\n    if (!owner.rowCount) return res.status(404).json({ error: 'Mangel nicht gefunden.' });",
    "const accessible = await canAccessCase(req.user.id, req.params.caseId);\n    if (!accessible) return res.status(404).json({ error: 'Mangel nicht gefunden.' });",
    'event access'
)
server = replace_once(
    server,
    "const owner = await pool.query('SELECT 1 FROM defect_cases WHERE id=$1 AND user_id=$2', [req.params.caseId, req.user.id]);\n    if (!owner.rowCount) return res.status(404).json({ error: 'Mangel nicht gefunden.' });",
    "const accessible = await canAccessCase(req.user.id, req.params.caseId);\n    if (!accessible) return res.status(404).json({ error: 'Mangel nicht gefunden.' });",
    'attachment upload access'
)
server = replace_once(
    server,
    "const result = await pool.query('SELECT * FROM attachments WHERE id=$1 AND user_id=$2', [req.params.attachmentId, req.user.id]);",
    "const result = await pool.query(`SELECT a.* FROM attachments a JOIN defect_cases c ON c.id=a.case_id WHERE a.id=$1 AND (c.user_id=$2 OR (c.organization_id IS NOT NULL AND EXISTS (SELECT 1 FROM organization_memberships om WHERE om.organization_id=c.organization_id AND om.user_id=$2)))`, [req.params.attachmentId, req.user.id]);",
    'attachment read access'
)
server = replace_once(
    server,
    "pool.query('SELECT * FROM defect_cases WHERE id=$1 AND user_id=$2', [req.params.caseId, req.user.id]),\n      pool.query('SELECT * FROM attachments WHERE case_id=$1 AND user_id=$2 ORDER BY created_at', [req.params.caseId, req.user.id])",
    "pool.query(`SELECT c.* FROM defect_cases c WHERE c.id=$1 AND (c.user_id=$2 OR (c.organization_id IS NOT NULL AND EXISTS (SELECT 1 FROM organization_memberships om WHERE om.organization_id=c.organization_id AND om.user_id=$2)))`, [req.params.caseId, req.user.id]),\n      pool.query('SELECT * FROM attachments WHERE case_id=$1 ORDER BY created_at', [req.params.caseId])",
    'pdf access'
)

old_logo = """      doc.roundedRect(left, 23, 32, 32, 6).fill(C.white);\n      doc.font('Helvetica-Bold').fontSize(13).fillColor(C.ink).text('MF', left + 5, 33, { width: 22, align: 'center', lineBreak: false });"""
new_logo = """      doc.roundedRect(left, 23, 32, 32, 6).fill(C.white);\n      // MängelFix-Dokumentlogo: Blatt + Haken statt Platzhalter 'MF'\n      doc.save();\n      doc.strokeColor(C.ink).lineWidth(1.4);\n      doc.roundedRect(left + 8, 29, 15, 19, 2).stroke();\n      doc.moveTo(left + 18, 29).lineTo(left + 23, 34).lineTo(left + 18, 34).stroke();\n      doc.strokeColor(C.blue).lineWidth(2.0);\n      doc.moveTo(left + 11, 40).lineTo(left + 15, 44).lineTo(left + 22, 36).stroke();\n      doc.restore();"""
server = replace_once(server, old_logo, new_logo, 'pdf logo')
server_path.write_text(server)

# --- React UI ---------------------------------------------------------------
app_path = Path('client/src/App.jsx')
app = app_path.read_text()
app = app.replace('<a href="/#funktionen">Funktionen</a>', '<a href="/#funktionen">Funktionen</a>\n        <a href="/#tarife">Tarife</a>', 1)

pricing = r'''

        <section className="pricingSection" id="tarife">
          <div className="sectionIntro"><span>TARIFE</span><h2>Für den einzelnen Mieter. Und für ganze Verwaltungen.</h2><p>MängelFix bekommt zwei klar getrennte Produktlinien. Die konkreten Preise legen wir vor dem Zahlungsstart fest.</p></div>
          <div className="pricingGrid">
            <article className="pricingCard privatePlan"><div className="planTag">PRIVAT</div><h3>MängelFix Privat</h3><p className="planLead">Für Mieter und private Nutzer, die ihre eigenen Vorgänge sauber dokumentieren möchten.</p><div className="planPrice"><strong>Einzeltarif</strong><span>1 persönliches Konto</span></div><ul><li>Eigene Mängel & Objekte</li><li>Fotos, Fristen und Verlauf</li><li>Professionelle PDF-Dokumentation</li><li>Persönliches Absenderprofil</li></ul><button onClick={() => navigate(user ? '/app' : '/registrieren')}>{user ? 'Zur App' : 'Privat starten'} →</button></article>
            <article className="pricingCard businessPlan"><div className="planTag">HAUSVERWALTUNG</div><h3>MängelFix Verwaltung</h3><p className="planLead">Für Hausverwaltungen, Vermieterbüros und Teams, die gemeinsam an Objekten und Vorgängen arbeiten.</p><div className="planPrice"><strong>Teamtarif</strong><span>Mehrere Mitarbeiterkonten</span></div><ul><li>Gemeinsamer Arbeitsbereich</li><li>Inhaber-, Admin- und Mitarbeiterrollen</li><li>Mitarbeiter selbst anlegen</li><li>Gemeinsamer Zugriff auf Mängel & Dokumente</li><li>Für viele Objekte skalierbar</li></ul><button onClick={() => navigate(user ? '/app' : '/registrieren')}>{user ? 'Team einrichten' : 'Verwaltung starten'} →</button></article>
          </div>
        </section>
'''
if 'id="tarife"' not in app:
    app = replace_once(app, '\n        <section className="landingCta">', pricing + '\n        <section className="landingCta">', 'pricing section')

team_view = r'''

function TeamView() {
  const [team, setTeam] = useState({ organization: null, members: [] });
  const [orgName, setOrgName] = useState('');
  const [member, setMember] = useState({ name: '', email: '', password: '', role: 'member' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function load() {
    try { setTeam(await api('/api/team')); }
    catch (err) { setError(err.message); }
  }
  useEffect(() => { load(); }, []);

  async function createOrganization(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try { await api('/api/team', { method: 'POST', body: JSON.stringify({ name: orgName }) }); setMessage('Hausverwaltungs-Arbeitsbereich angelegt. Ab jetzt werden neue Vorgänge mit deinem Team geteilt.'); setOrgName(''); await load(); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function createMember(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try { await api('/api/team/members', { method: 'POST', body: JSON.stringify(member) }); setMessage('Mitarbeiterkonto erstellt. Die Person kann sich sofort mit der angegebenen E-Mail und dem Startpasswort anmelden.'); setMember({ name: '', email: '', password: '', role: 'member' }); await load(); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  if (!team.organization) {
    return <div className="workspacePage"><div className="workspaceHeading"><div><span>HAUSVERWALTUNG</span><h1>Gemeinsam statt mit geteilten Passwörtern.</h1><p>Privatkonten bleiben persönlich. Für Verwaltungen richtest du einen gemeinsamen Arbeitsbereich mit eigenen Mitarbeiter-Logins ein.</p></div></div><div className="teamIntroGrid"><section className="workspacePanel teamSetup"><div className="panelHead"><div><span>TEAMTARIF</span><h2>Hausverwaltung einrichten</h2></div></div><p>Nach dem Einrichten sehen alle Teammitglieder die gemeinsamen Vorgänge der Verwaltung. Du wirst automatisch Inhaber.</p><form onSubmit={createOrganization}><label>Name der Hausverwaltung<input required placeholder="z. B. Muster Hausverwaltung GmbH" value={orgName} onChange={e => setOrgName(e.target.value)} /></label>{error && <div className="errorBox">{error}</div>}{message && <div className="successBox">{message}</div>}<button className="primaryButton" disabled={busy}>{busy ? 'Einrichten…' : 'Arbeitsbereich einrichten'}</button></form></section><aside className="teamBenefits"><span>HAUSVERWALTUNG</span><h3>Was der Teamtarif vorbereitet</h3><ul><li>Eigene Logins für Mitarbeiter</li><li>Rollen: Inhaber, Admin, Mitarbeiter</li><li>Gemeinsame Mängel und Dokumente</li><li>Kein Teilen eines Master-Passworts</li><li>Basis für spätere Objekt- und Rechteverwaltung</li></ul></aside></div></div>;
  }

  const canManage = ['owner', 'admin'].includes(team.organization.role);
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>TEAM</span><h1>{team.organization.name}</h1><p>Gemeinsamer Hausverwaltungs-Arbeitsbereich · Rolle: {team.organization.role === 'owner' ? 'Inhaber' : team.organization.role === 'admin' ? 'Admin' : 'Mitarbeiter'}</p></div><div className="teamPlanBadge">VERWALTUNG · TEAMTARIF</div></div>{error && <div className="errorBox">{error}</div>}{message && <div className="successBox">{message}</div>}<div className="teamColumns"><section className="workspacePanel"><div className="panelHead"><div><span>MITARBEITER</span><h2>{team.members.length} Teammitglied{team.members.length === 1 ? '' : 'er'}</h2></div></div><div className="memberList">{team.members.map(item => <div className="memberRow" key={item.id}><div>{item.name.slice(0,1).toUpperCase()}</div><p><b>{item.name}</b><span>{item.email}</span></p><strong>{item.role === 'owner' ? 'INHABER' : item.role === 'admin' ? 'ADMIN' : 'MITARBEITER'}</strong></div>)}</div></section>{canManage && <form className="workspacePanel addMemberForm" onSubmit={createMember}><div className="panelHead"><div><span>NEUER ZUGANG</span><h2>Mitarbeiter anlegen</h2></div></div><label>Name<input required value={member.name} onChange={e => setMember({ ...member, name: e.target.value })} /></label><label>E-Mail<input required type="email" value={member.email} onChange={e => setMember({ ...member, email: e.target.value })} /></label><label>Startpasswort<input required minLength="8" type="password" value={member.password} onChange={e => setMember({ ...member, password: e.target.value })} placeholder="Mindestens 8 Zeichen" /></label><label>Rolle<select value={member.role} onChange={e => setMember({ ...member, role: e.target.value })}><option value="member">Mitarbeiter</option><option value="admin">Admin</option></select></label><small>Das Startpasswort wird nicht angezeigt oder per E-Mail versendet. Teile es der Person über einen sicheren Weg mit.</small><button className="primaryButton" disabled={busy}>{busy ? 'Anlegen…' : 'Mitarbeiterkonto anlegen'}</button></form>}</div></div>;
}
'''
if 'function TeamView()' not in app:
    app = replace_once(app, '\nfunction Workspace({ user, setUser, onLogout, navigate }) {', team_view + '\nfunction Workspace({ user, setUser, onLogout, navigate }) {', 'team view')

app = app.replace("else if (view === 'documents') content = <DocumentsView cases={cases} profileComplete={profileComplete} onProfile={goProfile} />;\n  else content = <ProfileView user={user} onSaved={setUser} />;", "else if (view === 'documents') content = <DocumentsView cases={cases} profileComplete={profileComplete} onProfile={goProfile} />;\n  else if (view === 'team') content = <TeamView />;\n  else content = <ProfileView user={user} onSaved={setUser} />;", 1)
app = app.replace("<button className={view === 'documents' ? 'active' : ''} onClick={() => { setSelected(null); setView('documents'); }}><span>D</span>Dokumente</button></nav>", "<button className={view === 'documents' ? 'active' : ''} onClick={() => { setSelected(null); setView('documents'); }}><span>D</span>Dokumente</button><button className={view === 'team' ? 'active' : ''} onClick={() => { setSelected(null); setView('team'); }}><span>T</span>Team</button></nav>", 1)
app_path.write_text(app)

# --- Styling ---------------------------------------------------------------
main_path = Path('client/src/main.jsx')
main = main_path.read_text()
if "./v03.css" not in main:
    main = main.replace("import './maengelfix-pro.css';", "import './maengelfix-pro.css';\nimport './v03.css';")
    main_path.write_text(main)

css_path = Path('client/src/v03.css')
css_path.write_text(r'''
/* MängelFix v0.3 — Tarif- und Teamoberfläche */
.pricingSection{padding:100px max(24px,6vw);background:var(--surface-2);border-top:1px solid var(--line)}
.pricingSection .sectionIntro{max-width:780px;margin:0 auto 48px;text-align:center}.pricingGrid{max-width:1120px;margin:auto;display:grid;grid-template-columns:1fr 1fr;gap:24px}.pricingCard{background:var(--surface);border:1px solid var(--line);padding:34px;position:relative;box-shadow:var(--shadow)}.pricingCard.businessPlan{border-top:5px solid var(--primary)}.pricingCard.privatePlan{border-top:5px solid var(--accent)}.planTag{font-size:10px;letter-spacing:.14em;font-weight:900;color:var(--muted)}.pricingCard h3{font-size:28px;margin:10px 0}.planLead{color:var(--muted);line-height:1.6;min-height:76px}.planPrice{border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:20px 0;margin:22px 0;display:flex;justify-content:space-between;gap:16px;align-items:end}.planPrice strong{font-size:22px}.planPrice span{color:var(--muted);font-size:12px}.pricingCard ul{list-style:none;padding:0;margin:0 0 28px;display:grid;gap:11px}.pricingCard li:before{content:'✓';color:var(--primary);font-weight:900;margin-right:10px}.pricingCard button{width:100%;border:0;padding:14px 16px;background:#18212b;color:white;font-weight:850;cursor:pointer}.businessPlan button{background:var(--primary)}
.teamIntroGrid,.teamColumns{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(320px,.9fr);gap:22px}.teamSetup form,.addMemberForm{display:grid;gap:15px}.teamBenefits{background:#18212b;color:white;padding:30px;border-top:5px solid var(--accent)}.teamBenefits>span,.teamPlanBadge{font-size:10px;letter-spacing:.13em;font-weight:900}.teamBenefits h3{font-size:25px;margin:12px 0 20px}.teamBenefits ul{padding-left:18px;line-height:2}.teamPlanBadge{background:var(--primary-soft);color:var(--primary);padding:10px 13px}.memberList{display:grid}.memberRow{display:grid;grid-template-columns:42px 1fr auto;gap:12px;align-items:center;padding:14px 0;border-bottom:1px solid var(--line)}.memberRow:last-child{border-bottom:0}.memberRow>div{width:38px;height:38px;display:grid;place-items:center;background:#18212b;color:white;font-weight:900}.memberRow p{margin:0;display:grid;gap:2px}.memberRow p span{color:var(--muted);font-size:12px}.memberRow strong{font-size:9px;letter-spacing:.08em;color:var(--primary);background:var(--primary-soft);padding:6px 8px}.addMemberForm>small{color:var(--muted);line-height:1.5}
/* Logo im Sidebar-Kopf stärker sichtbar */
.sidebarBrand .mfLogoMark{width:46px;height:46px}.sidebarBrand .mfLogoText strong{font-size:21px}.sidebarBrand{padding-top:4px!important}
@media(max-width:850px){.pricingGrid,.teamIntroGrid,.teamColumns{grid-template-columns:1fr}.planLead{min-height:0}.pricingSection{padding:70px 20px}}
''')

print('MängelFix v0.3 patch prepared')
