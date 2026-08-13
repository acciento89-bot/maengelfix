from pathlib import Path

root = Path('.')
server = root/'server/index.js'
schema = root/'server/schema.sql'
app = root/'client/src/App.jsx'
css = root/'client/src/maengelfix-pro.css'
env = root/'.env.example'

s = schema.read_text()
if '-- v0.7: Kommunikation und Kontomails' not in s:
    s += r'''

-- v0.7: Kommunikation und Kontomails
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at timestamptz;
ALTER TABLE case_events ADD COLUMN IF NOT EXISTS visibility text NOT NULL DEFAULT 'shared';

CREATE TABLE IF NOT EXISTS email_verification_tokens (
  id text PRIMARY KEY,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash text NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS email_verification_user_idx ON email_verification_tokens(user_id, expires_at DESC);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id text PRIMARY KEY,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash text NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS password_reset_user_idx ON password_reset_tokens(user_id, expires_at DESC);

CREATE TABLE IF NOT EXISTS case_messages (
  id text PRIMARY KEY,
  case_id text NOT NULL REFERENCES defect_cases(id) ON DELETE CASCADE,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  message text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS case_messages_case_idx ON case_messages(case_id, created_at);
'''
schema.write_text(s)

js = server.read_text()
js = js.replace("res.json({ ok: true, service: 'maengelfix', version: '0.6.0' });", "res.json({ ok: true, service: 'maengelfix', version: '0.7.0' });")

# enrich public user
old = """    phone: row.phone || ''\n  };"""
new = """    phone: row.phone || '',\n    emailVerified: Boolean(row.email_verified_at)\n  };"""
if old in js and 'emailVerified:' not in js:
    js = js.replace(old, new, 1)

# auth SELECTs include verification
js = js.replace('u.country, u.phone\n       FROM sessions', 'u.country, u.phone, u.email_verified_at\n       FROM sessions')
js = js.replace('street, postal_code, city, country, phone\n       FROM users WHERE email', 'street, postal_code, city, country, phone, email_verified_at\n       FROM users WHERE email')
js = js.replace('RETURNING id, name, email, street, postal_code, city, country, phone`,', 'RETURNING id, name, email, street, postal_code, city, country, phone, email_verified_at`,')

mail_helpers = r'''

function escapeHtml(value) {
  return String(value || '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));
}

async function sendAppMail({ to, subject, heading, text, buttonLabel, buttonUrl }) {
  if (!mailer || !to) return false;
  const safeHeading=escapeHtml(heading || subject);
  const safeText=escapeHtml(text).replace(/\n/g,'<br>');
  const button=buttonUrl ? `<p style="margin:28px 0"><a href="${escapeHtml(buttonUrl)}" style="background:#2457d6;color:white;text-decoration:none;padding:12px 18px;border-radius:6px;display:inline-block">${escapeHtml(buttonLabel || 'MängelFix öffnen')}</a></p>` : '';
  await mailer.sendMail({
    from: process.env.SMTP_FROM || 'MängelFix <noreply@kamilunavo.com>', to, subject,
    text: `${heading || subject}\n\n${text}${buttonUrl ? `\n\n${buttonLabel || 'MängelFix öffnen'}: ${buttonUrl}` : ''}`,
    html: `<div style="font-family:Arial,sans-serif;max-width:620px;margin:auto;color:#18212b"><div style="font-weight:700;font-size:20px;margin-bottom:24px">MängelFix</div><h2>${safeHeading}</h2><p style="line-height:1.6">${safeText}</p>${button}<p style="color:#6f7a86;font-size:12px;margin-top:32px">Diese Nachricht wurde automatisch von MängelFix gesendet.</p></div>`
  });
  return true;
}

async function issueVerification(userId, email, name) {
  if (!mailer) return false;
  await pool.query(`UPDATE email_verification_tokens SET expires_at=now() WHERE user_id=$1 AND used_at IS NULL AND expires_at>now()`, [userId]);
  const token=crypto.randomBytes(32).toString('base64url');
  await pool.query(`INSERT INTO email_verification_tokens (id,user_id,token_hash,expires_at) VALUES ($1,$2,$3,now()+interval '24 hours')`, [id(),userId,tokenHash(token)]);
  return sendAppMail({to:email,subject:'E-Mail-Adresse für MängelFix bestätigen',heading:`Hallo ${name || ''}`,text:'Bitte bestätige deine E-Mail-Adresse. Der Link ist 24 Stunden gültig.',buttonLabel:'E-Mail bestätigen',buttonUrl:`${appOrigin}/email-bestaetigen/${token}`});
}

async function notifyOrganization(organizationId, subject, text, caseId) {
  if (!mailer || !organizationId) return;
  const result=await pool.query(`SELECT DISTINCT u.email FROM organization_memberships om JOIN users u ON u.id=om.user_id WHERE om.organization_id=$1`, [organizationId]);
  await Promise.allSettled(result.rows.map(row=>sendAppMail({to:row.email,subject,heading:subject,text,buttonLabel:'Vorgang öffnen',buttonUrl:`${appOrigin}/app?case=${caseId}`})));
}

async function tenantOwnerForCase(caseId) {
  const result=await pool.query(`SELECT u.id,u.name,u.email,c.title,c.status,c.organization_id,c.submitted_by_tenant,o.name AS organization_name FROM defect_cases c JOIN users u ON u.id=c.user_id LEFT JOIN organizations o ON o.id=c.organization_id WHERE c.id=$1`, [caseId]);
  return result.rows[0] || null;
}
'''
anchor = "async function sendTenantInvitationMail({ to, tenantName, organizationName, propertyName, unitLabel, inviteUrl }) {"
if 'function escapeHtml(value)' not in js and anchor in js:
    js = js.replace(anchor, mail_helpers + '\n' + anchor, 1)

# register: issue verification after session
needle = """    await createSession(userId, res);\n    res.status(201).json({ user: publicUser(result.rows[0]) });"""
repl = """    await createSession(userId, res);\n    try { await issueVerification(userId, email, name); } catch (mailError) { console.error('Verification mail failed', mailError); }\n    res.status(201).json({ user: publicUser(result.rows[0]), verificationMailSent: Boolean(mailer) });"""
if needle in js:
    js = js.replace(needle, repl, 1)

# account mail routes before logout
anchor = "app.post('/api/auth/logout', auth, async (req, res, next) => {"
routes = r'''
app.post('/api/auth/resend-verification', auth, async (req,res,next)=>{
  try {
    if (req.user.email_verified_at) return res.json({ok:true,alreadyVerified:true});
    const sent=await issueVerification(req.user.id,req.user.email,req.user.name);
    res.json({ok:true,sent});
  } catch(error){next(error);}
});

app.get('/api/auth/verify-email/:token', async (req,res,next)=>{
  const client=await pool.connect();
  try {
    await client.query('BEGIN');
    const result=await client.query(`SELECT * FROM email_verification_tokens WHERE token_hash=$1 FOR UPDATE`,[tokenHash(req.params.token)]);
    if(!result.rowCount){await client.query('ROLLBACK');return res.status(404).json({error:'Bestätigungslink nicht gefunden.'});}
    const token=result.rows[0];
    if(token.used_at || new Date(token.expires_at)<=new Date()){await client.query('ROLLBACK');return res.status(410).json({error:'Dieser Bestätigungslink ist abgelaufen oder wurde bereits verwendet.'});}
    await client.query('UPDATE users SET email_verified_at=now() WHERE id=$1',[token.user_id]);
    await client.query('UPDATE email_verification_tokens SET used_at=now() WHERE id=$1',[token.id]);
    await client.query('COMMIT');
    res.json({ok:true});
  } catch(error){await client.query('ROLLBACK');next(error);} finally{client.release();}
});

app.post('/api/auth/forgot-password', async (req,res,next)=>{
  try {
    const email=cleanText(req.body.email,254)?.toLowerCase();
    const result=await pool.query('SELECT id,name,email FROM users WHERE email=$1',[email]);
    if(result.rowCount && mailer){
      const user=result.rows[0];
      await pool.query(`UPDATE password_reset_tokens SET expires_at=now() WHERE user_id=$1 AND used_at IS NULL AND expires_at>now()`,[user.id]);
      const token=crypto.randomBytes(32).toString('base64url');
      await pool.query(`INSERT INTO password_reset_tokens (id,user_id,token_hash,expires_at) VALUES ($1,$2,$3,now()+interval '60 minutes')`,[id(),user.id,tokenHash(token)]);
      await sendAppMail({to:user.email,subject:'MängelFix Passwort zurücksetzen',heading:'Passwort zurücksetzen',text:'Du hast ein neues Passwort angefordert. Der Link ist 60 Minuten gültig. Wenn du das nicht warst, kannst du diese E-Mail ignorieren.',buttonLabel:'Neues Passwort festlegen',buttonUrl:`${appOrigin}/passwort-zuruecksetzen/${token}`});
    }
    res.json({ok:true,message:'Wenn ein Konto mit dieser E-Mail existiert, wurde eine Nachricht versendet.'});
  } catch(error){next(error);}
});

app.post('/api/auth/reset-password/:token', async (req,res,next)=>{
  const client=await pool.connect();
  try {
    const password=String(req.body.password||'');
    if(password.length<8) return res.status(400).json({error:'Das neue Passwort muss mindestens 8 Zeichen haben.'});
    await client.query('BEGIN');
    const result=await client.query(`SELECT * FROM password_reset_tokens WHERE token_hash=$1 FOR UPDATE`,[tokenHash(req.params.token)]);
    if(!result.rowCount){await client.query('ROLLBACK');return res.status(404).json({error:'Link nicht gefunden.'});}
    const token=result.rows[0];
    if(token.used_at || new Date(token.expires_at)<=new Date()){await client.query('ROLLBACK');return res.status(410).json({error:'Dieser Link ist abgelaufen oder wurde bereits verwendet.'});}
    const credentials=await makePassword(password);
    await client.query('UPDATE users SET password_salt=$2,password_hash=$3 WHERE id=$1',[token.user_id,credentials.salt,credentials.hash]);
    await client.query('UPDATE password_reset_tokens SET used_at=now() WHERE id=$1',[token.id]);
    await client.query('DELETE FROM sessions WHERE user_id=$1',[token.user_id]);
    await client.query('COMMIT');
    res.json({ok:true});
  } catch(error){await client.query('ROLLBACK');next(error);} finally{client.release();}
});

'''
if "'/api/auth/forgot-password'" not in js and anchor in js:
    js = js.replace(anchor, routes + anchor, 1)

# notify org on invitation acceptance
needle = """    await client.query('COMMIT');\n    res.json({ link: linked.rows[0] });"""
repl = """    await client.query('COMMIT');\n    const orgInfo=await pool.query('SELECT name FROM organizations WHERE id=$1',[inv.organization_id]);\n    try { await notifyOrganization(inv.organization_id,'Mieter-Verknüpfung bestätigt',`${req.user.name} hat die digitale Verbindung zur Einheit bestätigt.`, inv.unit_id); } catch(mailError){ console.error('Acceptance notification failed',mailError); }\n    res.json({ link: linked.rows[0] });"""
if needle in js:
    js = js.replace(needle, repl, 1)

# new tenant defect notification after commit
needle = """    await client.query('COMMIT');\n    res.status(201).json({ case: result.rows[0] });"""
repl = """    await client.query('COMMIT');\n    if (destination) { try { await notifyOrganization(destination.organization_id,`Neuer Mangel: ${title}`,`${req.user.name} hat einen neuen Mangel für ${destination.property_name} · ${destination.unit_label} digital übermittelt.`,caseId); } catch(mailError){ console.error('New case notification failed',mailError); } }\n    res.status(201).json({ case: result.rows[0] });"""
# replace second occurrence? register also same status 201 but exact includes client commit, likely cases only
if needle in js:
    js = js.replace(needle, repl, 1)

# detail: filter internal events and include messages + viewer role
old = """    const [events, attachments] = await Promise.all([\n      pool.query('SELECT e.*, u.name AS actor_name FROM case_events e LEFT JOIN users u ON u.id=e.user_id WHERE e.case_id = $1 ORDER BY e.created_at DESC', [req.params.caseId]),\n      pool.query('SELECT id, original_name, mime_type, size_bytes, created_at FROM attachments WHERE case_id = $1 ORDER BY created_at', [req.params.caseId])\n    ]);\n    res.json({ case: result.rows[0], events: events.rows, attachments: attachments.rows });"""
new = """    const viewerOrganization = await organizationForUser(req.user.id);\n    const viewerIsOrganization = Boolean(viewerOrganization && viewerOrganization.id === result.rows[0].organization_id);\n    const [events, attachments, messages] = await Promise.all([\n      pool.query(`SELECT e.*, u.name AS actor_name FROM case_events e LEFT JOIN users u ON u.id=e.user_id WHERE e.case_id=$1 AND ($2::boolean=true OR e.visibility='shared') ORDER BY e.created_at DESC`, [req.params.caseId, viewerIsOrganization]),\n      pool.query('SELECT id, original_name, mime_type, size_bytes, created_at FROM attachments WHERE case_id = $1 ORDER BY created_at', [req.params.caseId]),\n      pool.query('SELECT m.*,u.name AS actor_name FROM case_messages m JOIN users u ON u.id=m.user_id WHERE m.case_id=$1 ORDER BY m.created_at', [req.params.caseId])\n    ]);\n    res.json({ case: result.rows[0], events: events.rows, attachments: attachments.rows, messages: messages.rows, viewerRole: viewerIsOrganization ? 'management' : 'tenant' });"""
if old in js:
    js = js.replace(old, new, 1)

# status notifications to tenant
needle = """      await pool.query(\n        'INSERT INTO case_events (id, case_id, user_id, event_type, note) VALUES ($1,$2,$3,$4,$5)',\n        [id(), req.params.caseId, req.user.id, 'status', `Status geändert: ${nextStatus}`]\n      );\n    }\n    res.json({ case: result.rows[0] });"""
repl = """      await pool.query(\n        'INSERT INTO case_events (id, case_id, user_id, event_type, note, visibility) VALUES ($1,$2,$3,$4,$5,\'shared\')',\n        [id(), req.params.caseId, req.user.id, 'status', `Status geändert: ${nextStatus}`]\n      );\n      if (old.submitted_by_tenant) {\n        const owner=await tenantOwnerForCase(req.params.caseId);\n        if(owner && owner.id!==req.user.id){ try { await sendAppMail({to:owner.email,subject:`Status aktualisiert: ${old.title}`,heading:'Deine Mängelmeldung wurde aktualisiert',text:`Der Status von „${old.title}“ wurde geändert. Neuer Status: ${nextStatus}.`,buttonLabel:'Vorgang öffnen',buttonUrl:`${appOrigin}/app?case=${req.params.caseId}`}); } catch(mailError){console.error('Status mail failed',mailError);} }\n      }\n    }\n    res.json({ case: result.rows[0] });"""
if needle in js:
    js = js.replace(needle, repl, 1)

# internal/shared event endpoint behavior
old = """    const result = await pool.query(\n      'INSERT INTO case_events (id, case_id, user_id, event_type, note) VALUES ($1,$2,$3,$4,$5) RETURNING *',\n      [id(), req.params.caseId, req.user.id, 'note', note]\n    );"""
new = """    const viewerOrganization=await organizationForUser(req.user.id);\n    const isManagement=Boolean(viewerOrganization && viewerOrganization.id===accessible.organization_id);\n    const visibility=isManagement ? 'internal' : 'shared';\n    const result = await pool.query(\n      'INSERT INTO case_events (id, case_id, user_id, event_type, note, visibility) VALUES ($1,$2,$3,$4,$5,$6) RETURNING *',\n      [id(), req.params.caseId, req.user.id, 'note', note, visibility]\n    );"""
if old in js:
    js = js.replace(old, new, 1)

# messages endpoint before storage
anchor = "const storage = multer.diskStorage({"
message_routes = r'''
app.post('/api/cases/:caseId/messages', auth, async (req,res,next)=>{
  try {
    const accessible=await canAccessCase(req.user.id,req.params.caseId);
    if(!accessible) return res.status(404).json({error:'Mangel nicht gefunden.'});
    if(!accessible.submitted_by_tenant) return res.status(400).json({error:'Gemeinsame Nachrichten sind nur bei digital verbundenen Mietervorgängen verfügbar.'});
    const message=cleanText(req.body.message,4000);
    if(!message) return res.status(400).json({error:'Nachricht darf nicht leer sein.'});
    const result=await pool.query(`INSERT INTO case_messages (id,case_id,user_id,message) VALUES ($1,$2,$3,$4) RETURNING *`,[id(),req.params.caseId,req.user.id,message]);
    await pool.query('UPDATE defect_cases SET updated_at=now() WHERE id=$1',[req.params.caseId]);
    const viewerOrganization=await organizationForUser(req.user.id);
    const fromManagement=Boolean(viewerOrganization && viewerOrganization.id===accessible.organization_id);
    try {
      if(fromManagement){
        const owner=await tenantOwnerForCase(req.params.caseId);
        if(owner) await sendAppMail({to:owner.email,subject:`Neue Nachricht zu: ${accessible.title}`,heading:'Neue Nachricht deiner Hausverwaltung',text:message,buttonLabel:'Nachricht öffnen',buttonUrl:`${appOrigin}/app?case=${req.params.caseId}`});
      } else {
        await notifyOrganization(accessible.organization_id,`Neue Mieternachricht: ${accessible.title}`,`${req.user.name}: ${message}`,req.params.caseId);
      }
    } catch(mailError){console.error('Message mail failed',mailError);}
    res.status(201).json({message:result.rows[0]});
  } catch(error){next(error);}
});

'''
if "'/api/cases/:caseId/messages'" not in js and anchor in js:
    js = js.replace(anchor, message_routes + anchor, 1)

server.write_text(js)

# Frontend
jsx = app.read_text()
# forgot password link in auth
old = """          <div className=\"authSwitch\">{register ? 'Du hast bereits ein Konto?' : 'Noch kein MängelFix-Konto?'} <button onClick={() => navigate(register ? '/anmelden' : '/registrieren')}>{register ? 'Anmelden' : 'Kostenlos registrieren'}</button></div>"""
new = """          {!register && <div className=\"authForgot\"><button onClick={() => navigate('/passwort-vergessen')}>Passwort vergessen?</button></div>}\n          <div className=\"authSwitch\">{register ? 'Du hast bereits ein Konto?' : 'Noch kein MängelFix-Konto?'} <button onClick={() => navigate(register ? '/anmelden' : '/registrieren')}>{register ? 'Anmelden' : 'Kostenlos registrieren'}</button></div>"""
if old in jsx:
    jsx = jsx.replace(old,new,1)

# add account pages before LegalPage
anchor = "function LegalPage({ type, navigate }) {"
pages = r'''
function SimpleAccountPage({ mode, token, navigate }) {
  const [email,setEmail]=useState(''); const [password,setPassword]=useState(''); const [message,setMessage]=useState(''); const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
  useEffect(()=>{ if(mode==='verify'&&token){ setBusy(true); api(`/api/auth/verify-email/${token}`).then(()=>setMessage('Deine E-Mail-Adresse wurde bestätigt.')).catch(e=>setError(e.message)).finally(()=>setBusy(false)); } },[mode,token]);
  async function submit(e){e.preventDefault();setBusy(true);setError('');setMessage('');try{if(mode==='forgot'){const d=await api('/api/auth/forgot-password',{method:'POST',body:JSON.stringify({email})});setMessage(d.message);}else if(mode==='reset'){await api(`/api/auth/reset-password/${token}`,{method:'POST',body:JSON.stringify({password})});setMessage('Dein Passwort wurde geändert. Du kannst dich jetzt anmelden.');}}catch(x){setError(x.message)}finally{setBusy(false)}}
  const title=mode==='forgot'?'Passwort vergessen':mode==='reset'?'Neues Passwort':'E-Mail bestätigen';
  return <div className="authStandalone"><PublicHeader navigate={navigate}/><main className="authStage accountActionStage"><section className="authPitch"><div className="landingEyebrow"><span/> MÄNGELFIX KONTO</div><h1>{title}</h1><p>{mode==='forgot'?'Wir senden dir einen sicheren Link zum Zurücksetzen.':mode==='reset'?'Lege ein neues Passwort mit mindestens 8 Zeichen fest.':'Wir prüfen deinen Bestätigungslink.'}</p></section><section className="authBox"><div className="authBoxHead"><span>KONTO</span><h2>{title}</h2></div>{mode!=='verify'&&<form onSubmit={submit} className="formStack">{mode==='forgot'?<label>E-Mail<input required type="email" value={email} onChange={e=>setEmail(e.target.value)}/></label>:<label>Neues Passwort<input required minLength="8" type="password" value={password} onChange={e=>setPassword(e.target.value)}/></label>}<button className="primaryButton authSubmit" disabled={busy}>{busy?'Einen Moment…':mode==='forgot'?'Link anfordern':'Passwort speichern'}</button></form>}{busy&&mode==='verify'&&<p>Bestätigung wird geprüft…</p>}{error&&<div className="errorBox">{error}</div>}{message&&<div className="successBox">{message}</div>}<div className="authSwitch"><button onClick={()=>navigate('/anmelden')}>Zur Anmeldung</button></div></section></main><PublicFooter navigate={navigate}/></div>;
}

'''
if 'function SimpleAccountPage' not in jsx and anchor in jsx:
    jsx = jsx.replace(anchor,pages+anchor,1)

# CaseDetail communication state and function
old = """  const [note, setNote] = useState('');\n  const profileComplete"""
new = """  const [note, setNote] = useState('');\n  const [sharedMessage,setSharedMessage]=useState('');\n  const profileComplete"""
if old in jsx:
    jsx = jsx.replace(old,new,1)

anchor = """  async function uploadImages(event) {"""
message_func = r'''  async function sendSharedMessage(event) {
    event.preventDefault(); if (!sharedMessage.trim()) return;
    setBusy(true); setError('');
    try { await api(`/api/cases/${caseId}/messages`, { method:'POST', body:JSON.stringify({message:sharedMessage}) }); setSharedMessage(''); await load(); onUpdated(); }
    catch(err){setError(err.message);} finally{setBusy(false);}
  }

'''
if 'async function sendSharedMessage' not in jsx and anchor in jsx:
    jsx = jsx.replace(anchor,message_func+anchor,1)

# Inject communication before BEWEISSICHERUNG
anchor = """      <section className=\"contentCard\"><div className=\"sectionTitle\"><div><div className=\"cardKicker\">BEWEISSICHERUNG</div>"""
communication = r'''      {item.submitted_by_tenant&&<section className="contentCard communicationCard"><div className="sectionTitle"><div><div className="cardKicker">KOMMUNIKATION</div><h3>{data.viewerRole==='management'?'Nachrichten an den Mieter':'Nachrichten mit der Hausverwaltung'}</h3><p className="muted">Diese Nachrichten sind für beide Seiten sichtbar und werden getrennt von internen Notizen gespeichert.</p></div></div><div className="messageThread">{(data.messages||[]).length?(data.messages||[]).map(msg=><div key={msg.id} className={`sharedMessage ${msg.user_id===user.id?'own':''}`}><div><b>{msg.actor_name}</b><span>{new Date(msg.created_at).toLocaleString('de-DE')}</span></div><p>{msg.message}</p></div>):<div className="emptyMini">Noch keine gemeinsamen Nachrichten.</div>}</div><form className="messageComposer" onSubmit={sendSharedMessage}><textarea rows="3" placeholder={data.viewerRole==='management'?'Nachricht an den Mieter…':'Nachricht an die Hausverwaltung…'} value={sharedMessage} onChange={e=>setSharedMessage(e.target.value)}/><button className="primaryButton" disabled={busy}>Nachricht senden</button></form></section>}
'''
if 'communicationCard' not in jsx and anchor in jsx:
    jsx = jsx.replace(anchor,communication+anchor,1)

# chronology helper text internal for management
jsx = jsx.replace("<p className=\"muted\">Notizen und Statusänderungen bleiben nachvollziehbar.</p>", "<p className=\"muted\">{data.viewerRole==='management'&&item.submitted_by_tenant?'Interne Notizen sind nur für das Verwaltungsteam sichtbar. Statusänderungen bleiben für den Mieter nachvollziehbar.':'Notizen und Statusänderungen bleiben nachvollziehbar.'}</p>", 1)
jsx = jsx.replace("placeholder=\"Neue Notiz, z. B. Hausverwaltung telefonisch erreicht…\"", "placeholder={data.viewerRole==='management'&&item.submitted_by_tenant?'Interne Notiz – für den Mieter nicht sichtbar…':'Neue Notiz, z. B. Hausverwaltung telefonisch erreicht…'}", 1)

# profile verification notice/action
old = """<div className=\"profileActions\"><button className=\"primaryButton\" disabled={busy}>{busy ? 'Speichern…' : 'Profil speichern'}</button></div>"""
new = """{!user.emailVerified&&<div className=\"verificationNotice\"><div><b>E-Mail noch nicht bestätigt</b><span>Bestätige deine Adresse für Kontosicherheit und Benachrichtigungen.</span></div><button type=\"button\" className=\"secondaryButton\" onClick={async()=>{try{const d=await api('/api/auth/resend-verification',{method:'POST'});setMessage(d.sent?'Bestätigungs-E-Mail wurde versendet.':'Mailversand ist noch nicht konfiguriert.');}catch(e){setError(e.message)}}}>Bestätigung senden</button></div>}<div className=\"profileActions\"><button className=\"primaryButton\" disabled={busy}>{busy ? 'Speichern…' : 'Profil speichern'}</button></div>"""
if old in jsx:
    jsx = jsx.replace(old,new,1)

# routes in App
needle = """  if (path === '/anmelden') return <Auth mode=\"login\" onSignedIn={user => setState({ loading: false, user })} navigate={navigate} />;"""
routes_jsx = """  if (path === '/passwort-vergessen') return <SimpleAccountPage mode=\"forgot\" navigate={navigate} />;\n  if (path.startsWith('/passwort-zuruecksetzen/')) return <SimpleAccountPage mode=\"reset\" token={path.split('/').pop()} navigate={navigate} />;\n  if (path.startsWith('/email-bestaetigen/')) return <SimpleAccountPage mode=\"verify\" token={path.split('/').pop()} navigate={navigate} />;\n"""
if "'/passwort-vergessen'" not in jsx and needle in jsx:
    jsx = jsx.replace(needle,routes_jsx+needle,1)

# Query case opening on workspace init
old = """  useEffect(() => { loadCases(); api('/api/management/overview').then(setManagement).catch(()=>setManagement({organization:null})); }, []);"""
new = """  useEffect(() => { loadCases(); api('/api/management/overview').then(setManagement).catch(()=>setManagement({organization:null})); const params=new URLSearchParams(window.location.search); const caseId=params.get('case'); if(caseId)setSelected(caseId); }, []);"""
if old in jsx:
    jsx = jsx.replace(old,new,1)

app.write_text(jsx)

style = css.read_text()
if '/* v0.7 communication */' not in style:
    style += r'''

/* v0.7 communication */
.authForgot{margin:-2px 0 14px;text-align:right}.authForgot button{border:0;background:none;color:var(--blue,#2457d6);font-weight:700;cursor:pointer}.accountActionStage{min-height:620px}.communicationCard{border-top:3px solid #2457d6}.messageThread{display:flex;flex-direction:column;gap:12px;margin:18px 0;max-height:420px;overflow:auto;padding-right:4px}.sharedMessage{max-width:78%;background:#f2f4f7;border:1px solid #e0e5ea;border-radius:10px;padding:12px 14px}.sharedMessage.own{margin-left:auto;background:#eaf0ff;border-color:#cfdafe}.sharedMessage>div{display:flex;justify-content:space-between;gap:12px;font-size:12px;color:#6f7a86}.sharedMessage>div b{color:#18212b}.sharedMessage p{margin:7px 0 0;white-space:pre-wrap;line-height:1.5}.messageComposer{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:end}.messageComposer textarea{resize:vertical;min-height:78px}.verificationNotice{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:14px 16px;margin-top:18px;background:#fff7e8;border:1px solid #f1d79b;border-radius:8px}.verificationNotice div{display:flex;flex-direction:column;gap:3px}.verificationNotice span{font-size:13px;color:#6f7a86}@media(max-width:720px){.messageComposer{grid-template-columns:1fr}.sharedMessage{max-width:92%}.verificationNotice{align-items:flex-start;flex-direction:column}}
'''
css.write_text(style)

# env stays same, annotate
et = env.read_text()
if '# SMTP powers' not in et:
    et += '\n# SMTP powers invitations, verification, password reset and case notifications.\n'
env.write_text(et)
