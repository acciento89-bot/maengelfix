from pathlib import Path
import json
import re

root = Path('.')
server_path = root / 'server/index.js'
schema_path = root / 'server/schema.sql'
package_path = root / 'server/package.json'
app_path = root / 'client/src/App.jsx'
css_path = root / 'client/src/maengelfix-pro.css'

server = server_path.read_text()
schema = schema_path.read_text()
app = app_path.read_text()
css = css_path.read_text()
pkg = json.loads(package_path.read_text())

pkg['version'] = '0.21.0'
package_path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + '\n')
server = re.sub(r"version: '[^']+'", "version: '0.21.0'", server, count=1)

# Existing management trials must really have a 14-day window and Pro-sized trial capacity.
if '-- v0.21 account modes and management trial repair' not in schema:
    schema += """

-- v0.21 account modes and management trial repair
UPDATE organizations
SET plan_code = CASE WHEN plan_code='business_trial' THEN 'management_trial' ELSE plan_code END,
    trial_ends_at = COALESCE(trial_ends_at, created_at + interval '14 days'),
    max_members = CASE WHEN plan_code IN ('business_trial','management_trial') THEN 5 ELSE max_members END,
    max_properties = CASE WHEN plan_code IN ('business_trial','management_trial') THEN 100 ELSE max_properties END,
    max_units = CASE WHEN plan_code IN ('business_trial','management_trial') THEN 100 ELSE max_units END
WHERE subscription_status='trialing' AND subscription_provider IS NULL;
"""
schema_path.write_text(schema)

# Registration now decides the workspace up front. A management registration creates the
# organization and the real 14-day trial atomically with the user account.
register_route = r"""app.post('/api/auth/register', async (req, res, next) => {
  const client = await pool.connect();
  let transactionOpen = false;
  try {
    const accountType = req.body.accountType === 'management' ? 'management' : 'private';
    const name = cleanText(req.body.name, 120);
    const email = cleanText(req.body.email, 254)?.toLowerCase();
    const password = String(req.body.password || '');
    const organizationName = cleanText(req.body.organizationName, 180);

    if (!name || !email || !email.includes('@') || password.length < 8) {
      return res.status(400).json({ error: 'Name, gültige E-Mail und mindestens 8 Zeichen Passwort sind erforderlich.' });
    }
    if (accountType === 'management' && !organizationName) {
      return res.status(400).json({ error: 'Bitte gib den Namen deiner Hausverwaltung an.' });
    }

    await client.query('BEGIN');
    transactionOpen = true;
    const existing = await client.query('SELECT 1 FROM users WHERE email=$1', [email]);
    if (existing.rowCount) {
      await client.query('ROLLBACK'); transactionOpen = false;
      return res.status(409).json({ error: 'Für diese E-Mail existiert bereits ein Konto.' });
    }

    const credentials = await makePassword(password);
    const userId = id();
    const result = await client.query(
      `INSERT INTO users (id,name,email,password_salt,password_hash,country,onboarding_use_case,onboarding_completed_at)
       VALUES ($1,$2,$3,$4,$5,'Deutschland',$6,now())
       RETURNING id,name,email,street,postal_code,city,country,phone,email_verified_at,plan_code,subscription_status,subscription_current_period_end,onboarding_completed_at,onboarding_use_case`,
      [userId, name, email, credentials.salt, credentials.hash, accountType]
    );

    let organization = null;
    if (accountType === 'management') {
      const organizationId = id();
      const orgResult = await client.query(
        `INSERT INTO organizations
         (id,name,plan_code,created_by,subscription_status,trial_ends_at,max_members,max_properties,max_units)
         VALUES ($1,$2,'management_trial',$3,'trialing',now()+interval '14 days',5,100,100)
         RETURNING id,name,plan_code,subscription_status,trial_ends_at,max_members,max_properties,max_units`,
        [organizationId, organizationName, userId]
      );
      await client.query(
        `INSERT INTO organization_memberships (organization_id,user_id,role) VALUES ($1,$2,'owner')`,
        [organizationId, userId]
      );
      organization = { ...orgResult.rows[0], role: 'owner' };
    }

    await client.query('COMMIT');
    transactionOpen = false;
    await createSession(userId, res);
    try { await issueVerification(userId, email, name); } catch (mailError) { console.error('Verification mail failed', mailError); }
    res.status(201).json({ user: publicUser(result.rows[0]), accountType, organization, verificationMailSent: Boolean(mailer) });
  } catch (error) {
    if (transactionOpen) { try { await client.query('ROLLBACK'); } catch {} }
    next(error);
  } finally {
    client.release();
  }
});"""

pattern = r"app\.post\('/api/auth/register', async \(req, res, next\) => \{.*?\n\}\);\n\napp\.post\('/api/auth/login'"
match = re.search(pattern, server, flags=re.S)
if not match:
    raise SystemExit('registration route marker not found')
server = server[:match.start()] + register_route + "\n\napp.post('/api/auth/login'" + server[match.end():]

# If an existing private account deliberately changes to management in the introduction,
# create the management workspace immediately instead of sending it through the old half-state.
onboarding_route = r"""app.patch('/api/onboarding', auth, async (req,res,next)=>{
  const client = await pool.connect();
  let transactionOpen = false;
  try {
    const useCase = req.body.useCase === 'management' ? 'management' : 'private';
    const requestedOrganizationName = cleanText(req.body.organizationName,180) || `${req.user.name || 'Meine'} Hausverwaltung`;
    await client.query('BEGIN'); transactionOpen = true;

    if (useCase === 'management') {
      const existing = await client.query(
        `SELECT o.id FROM organization_memberships om JOIN organizations o ON o.id=om.organization_id
         WHERE om.user_id=$1 AND COALESCE(om.active,true)=true LIMIT 1`, [req.user.id]
      );
      if (!existing.rowCount) {
        const organizationId=id();
        await client.query(
          `INSERT INTO organizations (id,name,plan_code,created_by,subscription_status,trial_ends_at,max_members,max_properties,max_units)
           VALUES ($1,$2,'management_trial',$3,'trialing',now()+interval '14 days',5,100,100)`,
          [organizationId,requestedOrganizationName,req.user.id]
        );
        await client.query(`INSERT INTO organization_memberships (organization_id,user_id,role) VALUES ($1,$2,'owner')`,[organizationId,req.user.id]);
      }
    }

    const q=await client.query(
      `UPDATE users SET onboarding_use_case=$2,onboarding_completed_at=now() WHERE id=$1
       RETURNING id,name,email,street,postal_code,city,country,phone,email_verified_at,plan_code,subscription_status,subscription_current_period_end,onboarding_completed_at,onboarding_use_case`,
      [req.user.id,useCase]
    );
    await client.query('COMMIT'); transactionOpen=false;
    res.json({user:publicUser(q.rows[0])});
  } catch(e) {
    if(transactionOpen){try{await client.query('ROLLBACK')}catch{}}
    next(e);
  } finally { client.release(); }
});"""

pattern = r"app\.patch\('/api/onboarding'.*?\);\n\napp\.patch\('/api/profile'"
match = re.search(pattern, server, flags=re.S)
if not match:
    raise SystemExit('onboarding route marker not found')
server = server[:match.start()] + onboarding_route + "\n\napp.patch('/api/profile'" + server[match.end():]

# Team-created employee accounts are management accounts from their first login.
server = server.replace(
    "`INSERT INTO users (id,name,email,password_salt,password_hash,country) VALUES ($1,$2,$3,$4,$5,'Deutschland')`",
    "`INSERT INTO users (id,name,email,password_salt,password_hash,country,onboarding_use_case,onboarding_completed_at) VALUES ($1,$2,$3,$4,$5,'Deutschland','management',now())`"
)

# Creating a management workspace from an older private account also updates the account mode.
team_start = server.find("app.post('/api/team', auth")
if team_start != -1:
    team_end = server.find("app.post('/api/team/members'", team_start)
    block = server[team_start:team_end]
    marker = "V021_TEAM_ACCOUNT_MODE"
    if marker not in block:
        block = block.replace(
            "await pool.query('COMMIT');",
            "// V021_TEAM_ACCOUNT_MODE\n      await pool.query(`UPDATE users SET onboarding_use_case='management',onboarding_completed_at=COALESCE(onboarding_completed_at,now()) WHERE id=$1`,[req.user.id]);\n      await pool.query('COMMIT');",
            1
        )
        server = server[:team_start] + block + server[team_end:]

server_path.write_text(server)

# --- Web registration -------------------------------------------------------
new_auth = r"""function Auth({ mode, onSignedIn, navigate, initialAccountType = 'private' }) {
  const register = mode === 'register';
  const [accountType, setAccountType] = useState(initialAccountType);
  const [form, setForm] = useState({ name: '', email: '', password: '', organizationName: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (register) setAccountType(initialAccountType); }, [initialAccountType, register]);

  async function submit(event) {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      if (register && accountType === 'management' && !form.organizationName.trim()) {
        throw new Error('Bitte gib den Namen deiner Hausverwaltung an.');
      }
      const payload = register
        ? { name: form.name, email: form.email, password: form.password, accountType, organizationName: accountType === 'management' ? form.organizationName : undefined }
        : { email: form.email, password: form.password };
      const data = await api(register ? '/api/auth/register' : '/api/auth/login', { method: 'POST', body: JSON.stringify(payload) });
      onSignedIn(data.user);
      const pendingInvite = window.localStorage.getItem('maengelfix_pending_invite');
      navigate(pendingInvite ? `/einladung/${pendingInvite}` : '/app');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  const management = register && accountType === 'management';
  return (
    <div className="authStandalone">
      <PublicHeader navigate={navigate} />
      <main className="authStage">
        <section className="authPitch">
          <div className="landingEyebrow"><span /> {management ? 'MÄNGELFIX VERWALTUNG' : 'MÄNGELFIX KONTO'}</div>
          <h1>{register ? (management ? 'Deine Verwaltung. Ein eigener Arbeitsbereich.' : 'Deine Mängel. Ein Ort. Ein sauberer Verlauf.') : 'Willkommen zurück.'}</h1>
          <p>{register ? (management ? 'Starte direkt mit einem Verwaltungs-Arbeitsbereich. Die ersten 14 Tage sind kostenlos und enthalten alle Pro-Verwaltungsfunktionen.' : 'Erstelle dein persönliches Privatkonto für eigene Mängel, Belege und Dokumente.') : 'Öffne deine Vorgänge, Fristen und Dokumente.'}</p>
          <div className="authBenefits">
            {management ? <><span>✓ 14 Tage Verwaltung Pro testen</span><span>✓ Eigene Mitarbeiter-Logins & Rollen</span><span>✓ Objekte, Mieter, Aufgaben, Termine & Dienstleister</span></> : <><span>✓ Fälle & Fotos zentral gespeichert</span><span>✓ Professionelle PDF-Dokumentation</span><span>✓ Privat Free dauerhaft nutzbar</span></>}
          </div>
        </section>
        <section className="authBox">
          <div className="authBoxHead"><span>{register ? 'KONTO ERSTELLEN' : 'ANMELDEN'}</span><h2>{register ? (management ? 'Verwaltung kostenlos testen' : 'Privatkonto erstellen') : 'In dein Konto'}</h2></div>
          {register && <div className="accountTypePicker">
            <button type="button" className={accountType === 'private' ? 'accountTypeCard selected' : 'accountTypeCard'} onClick={() => setAccountType('private')}><span>PRIVAT</span><strong>Für eigene Mängel</strong><small>Dauerhaft kostenlos starten. Pro später optional.</small></button>
            <button type="button" className={accountType === 'management' ? 'accountTypeCard selected management' : 'accountTypeCard management'} onClick={() => setAccountType('management')}><span>HAUSVERWALTUNG</span><strong>Für Verwaltung & Team</strong><small>14 Tage alle Verwaltungsfunktionen testen.</small></button>
          </div>}
          <form onSubmit={submit} className="formStack">
            {register && <label>{management ? 'Dein Name' : 'Name'}<input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} autoComplete="name" placeholder="Vor- und Nachname" /></label>}
            {management && <label>Name der Hausverwaltung<input required value={form.organizationName} onChange={e => setForm({ ...form, organizationName: e.target.value })} placeholder="z. B. Muster Hausverwaltung GmbH" /></label>}
            <label>E-Mail<input required type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} autoComplete="email" placeholder="name@beispiel.de" /></label>
            <label>Passwort<input required minLength="8" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} autoComplete={register ? 'new-password' : 'current-password'} placeholder="Mindestens 8 Zeichen" /></label>
            {management && <div className="managementTrialHint"><b>14 Tage kostenlos</b><span>Keine Zahlung bei der Registrierung. Danach wählst du den passenden Verwaltungstarif.</span></div>}
            {error && <div className="errorBox">{error}</div>}
            <button className="primaryButton authSubmit" disabled={busy}>{busy ? 'Einen Moment…' : register ? (management ? '14 Tage kostenlos testen' : 'Privatkonto erstellen') : 'Anmelden'}</button>
          </form>
          {!register && <div className="authForgot"><button onClick={() => navigate('/passwort-vergessen')}>Passwort vergessen?</button></div>}
          <div className="authSwitch">{register ? 'Du hast bereits ein Konto?' : 'Noch kein MängelFix-Konto?'} <button onClick={() => navigate(register ? '/anmelden' : '/registrieren')}>{register ? 'Anmelden' : 'Kostenlos registrieren'}</button></div>
          <p className="legalHint">Mit der Nutzung gelten unsere <button onClick={() => navigate('/nutzungsbedingungen')}>Nutzungsbedingungen</button> und <button onClick={() => navigate('/datenschutz')}>Datenschutzhinweise</button>.</p>
        </section>
      </main>
      <PublicFooter navigate={navigate} />
    </div>
  );
}"""

pattern = r"function Auth\(\{ mode, onSignedIn, navigate \}\) \{.*?\n\}\n\nfunction SimpleAccountPage"
match = re.search(pattern, app, flags=re.S)
if not match:
    raise SystemExit('Auth component marker not found')
app = app[:match.start()] + new_auth + "\n\nfunction SimpleAccountPage" + app[match.end():]

# Dedicated registration URLs. /registrieren remains the neutral chooser.
old_route = "if (path === '/registrieren') return <Auth mode=\"register\" onSignedIn={user => setState({ loading: false, user })} navigate={navigate} />;"
new_route = """if (path === '/registrieren' || path === '/registrieren/privat' || path === '/registrieren/verwaltung') {
    const initialAccountType = path === '/registrieren/verwaltung' ? 'management' : 'private';
    return <Auth mode=\"register\" initialAccountType={initialAccountType} onSignedIn={user => setState({ loading: false, user })} navigate={navigate} />;
  }"""
if old_route not in app:
    raise SystemExit('registration root route marker not found')
app = app.replace(old_route, new_route, 1)

# Management pricing now goes directly to management registration.
app = app.replace(
    "<button className=\"managementStartButton\" onClick={() => navigate(user ? '/app' : '/registrieren')}",
    "<button className=\"managementStartButton\" onClick={() => navigate(user ? '/app' : '/registrieren/verwaltung')}",
    1
)

# Private pricing CTAs go directly to private registration when the exact current markup is present.
app = app.replace(
    "onClick={() => navigate(user ? '/app' : '/registrieren')}>{user ? 'Zur App' : 'Kostenlos starten'} →</button></article>",
    "onClick={() => navigate(user ? '/app' : '/registrieren/privat')}>{user ? 'Zur App' : 'Kostenlos starten'} →</button></article>",
    1
)
app = app.replace(
    "onClick={() => navigate(user ? '/app' : '/registrieren')}>{user ? 'Pro ansehen' : 'Privat Pro starten'} →</button></article>",
    "onClick={() => navigate(user ? '/app' : '/registrieren/privat')}>{user ? 'Pro ansehen' : 'Privat Pro starten'} →</button></article>",
    1
)

# Refresh management + entitlement state whenever the workspace changes. This fixes the
# exact bug where a newly created organization still looked like Privat Free until reload.
workspace_start = app.find('function Workspace({ user, setUser, onLogout, navigate }) {')
if workspace_start == -1:
    raise SystemExit('Workspace marker not found')
refresh_pos = app.find('async function refreshUnread()', workspace_start)
if refresh_pos == -1:
    raise SystemExit('refreshUnread marker not found')
refresh_line_end = app.find('\n', refresh_pos)
if 'V021_WORKSPACE_REFRESH' not in app[workspace_start:workspace_start+5000]:
    helper = """
  // V021_WORKSPACE_REFRESH
  async function refreshWorkspaceState(){
    const [managementResult,entitlementResult]=await Promise.allSettled([api('/api/management/overview'),api('/api/entitlements')]);
    if(managementResult.status==='fulfilled')setManagement(managementResult.value);else setManagement({organization:null});
    if(entitlementResult.status==='fulfilled')setEntitlements(entitlementResult.value);else setEntitlements({scope:'private',pro:false,usage:{activeCases:0},limits:{maxActiveCases:5,maxPhotosPerCase:3}});
  }
"""
    app = app[:refresh_line_end+1] + helper + app[refresh_line_end+1:]

profile_marker = '  const profileComplete = Boolean(user.street && user.postalCode && user.city);'
if 'useEffect(()=>{refreshWorkspaceState()},[view]);' not in app:
    if profile_marker not in app:
        raise SystemExit('profileComplete marker not found')
    app = app.replace(profile_marker, "  useEffect(()=>{refreshWorkspaceState()},[view]);\n" + profile_marker, 1)

app = app.replace(
    "const finishOnboarding=(updated,useCase)=>{setUser(updated);setShowOnboarding(false);if(useCase==='management'){setSelected(null);setView('team')}};",
    "const finishOnboarding=(updated,useCase)=>{setUser(updated);setShowOnboarding(false);if(useCase==='management'){setSelected(null);setView('overview');refreshWorkspaceState()}};",
    1
)

# Team setup immediately notifies the parent instead of leaving stale private state behind.
app = app.replace('function TeamView() {', 'function TeamView({ onWorkspaceChanged }) {', 1)
old_create = "try { await api('/api/team', { method: 'POST', body: JSON.stringify({ name: orgName }) }); setMessage('Hausverwaltungs-Arbeitsbereich angelegt. Ab jetzt werden neue Vorgänge mit deinem Team geteilt.'); setOrgName(''); await load(); }"
new_create = "try { await api('/api/team', { method: 'POST', body: JSON.stringify({ name: orgName }) }); setMessage('Hausverwaltungs-Arbeitsbereich angelegt. Deine 14-Tage-Testphase ist jetzt aktiv.'); setOrgName(''); await load(); await onWorkspaceChanged?.(); }"
if old_create in app:
    app = app.replace(old_create, new_create, 1)
app = app.replace("else if (view === 'team') content = <TeamView />;", "else if (view === 'team') content = <TeamView onWorkspaceChanged={refreshWorkspaceState} />;", 1)

app_path.write_text(app)

if '/* v0.21 account type registration */' not in css:
    css += r'''

/* v0.21 account type registration */
.accountTypePicker{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 0 18px}.accountTypeCard{appearance:none;text-align:left;border:1px solid #d8dfe5;background:#f8fafb;border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:4px;cursor:pointer;color:#18212b}.accountTypeCard span{font-size:10px;font-weight:900;letter-spacing:.12em;color:#6f7a86}.accountTypeCard strong{font-size:15px}.accountTypeCard small{font-size:12px;line-height:1.35;color:#68747f}.accountTypeCard:hover{border-color:#aebbd0}.accountTypeCard.selected{border:2px solid #2457d6;background:#f3f6ff;padding:13px}.accountTypeCard.management.selected{box-shadow:0 0 0 3px rgba(36,87,214,.08)}.managementTrialHint{display:flex;flex-direction:column;gap:3px;padding:12px 14px;border-radius:9px;background:#edf3ff;border:1px solid #ceddff}.managementTrialHint b{color:#173fa8}.managementTrialHint span{font-size:12px;color:#566575;line-height:1.4}@media(max-width:640px){.accountTypePicker{grid-template-columns:1fr}}
'''
css_path.write_text(css)

print('v0.21 separate private/management registration and trial state prepared')
