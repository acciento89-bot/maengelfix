from pathlib import Path
import json

root=Path('.')
schema_p=root/'server/schema.sql'; server_p=root/'server/index.js'; app_p=root/'client/src/App.jsx'; css_p=root/'client/src/maengelfix-pro.css'; pkg_p=root/'server/package.json'
schema=schema_p.read_text(); server=server_p.read_text(); app=app_p.read_text(); css=css_p.read_text(); pkg=json.loads(pkg_p.read_text())

if '-- v0.10: Konto, Datenschutz und Team-Lifecycle' not in schema:
    schema += '''\n\n-- v0.10: Konto, Datenschutz und Team-Lifecycle\nALTER TABLE organization_memberships ADD COLUMN IF NOT EXISTS active boolean NOT NULL DEFAULT true;\nALTER TABLE organization_memberships ADD COLUMN IF NOT EXISTS deactivated_at timestamptz;\nALTER TABLE organization_memberships ADD COLUMN IF NOT EXISTS deactivated_by text REFERENCES users(id) ON DELETE SET NULL;\nALTER TABLE tenant_links ADD COLUMN IF NOT EXISTS disconnected_at timestamptz;\nALTER TABLE tenant_links ADD COLUMN IF NOT EXISTS disconnected_by text REFERENCES users(id) ON DELETE SET NULL;\n'''
schema_p.write_text(schema)

pkg['version']='0.10.0'; pkg_p.write_text(json.dumps(pkg,ensure_ascii=False,indent=2)+'\n')

# Make organization lookup respect deactivated memberships.
server=server.replace("WHERE om.user_id=$1", "WHERE om.user_id=$1 AND COALESCE(om.active,true)=true", 1)
server=server.replace("SELECT u.id, u.name, u.email, om.role, om.created_at", "SELECT u.id, u.name, u.email, om.role, om.created_at, COALESCE(om.active,true) AS active, om.deactivated_at")

anchor="app.get('/api/team', auth, async (req, res, next) => {"
if "app.post('/api/account/change-password'" not in server:
    endpoints=r'''app.post('/api/account/change-password', auth, async (req,res,next)=>{
  try {
    const current=String(req.body.currentPassword||''); const nextPassword=String(req.body.newPassword||'');
    if(nextPassword.length<8) return res.status(400).json({error:'Das neue Passwort muss mindestens 8 Zeichen haben.'});
    const r=await pool.query('SELECT password_salt,password_hash FROM users WHERE id=$1',[req.user.id]);
    if(!r.rowCount || !(await verifyPassword(current,r.rows[0].password_salt,r.rows[0].password_hash))) return res.status(401).json({error:'Das aktuelle Passwort ist nicht korrekt.'});
    const c=await makePassword(nextPassword); await pool.query('UPDATE users SET password_salt=$2,password_hash=$3 WHERE id=$1',[req.user.id,c.salt,c.hash]);
    const token=req.cookies[cookieName]; await pool.query('DELETE FROM sessions WHERE user_id=$1 AND token_hash<>$2',[req.user.id, token?tokenHash(token):'']);
    res.json({ok:true});
  } catch(error){next(error)}
});

app.patch('/api/account/email', auth, async (req,res,next)=>{
  try {
    const password=String(req.body.password||''); const email=cleanText(req.body.email,254)?.toLowerCase();
    if(!email||!email.includes('@')) return res.status(400).json({error:'Bitte gib eine gültige E-Mail-Adresse an.'});
    const r=await pool.query('SELECT password_salt,password_hash FROM users WHERE id=$1',[req.user.id]);
    if(!(await verifyPassword(password,r.rows[0].password_salt,r.rows[0].password_hash))) return res.status(401).json({error:'Das Passwort ist nicht korrekt.'});
    const exists=await pool.query('SELECT 1 FROM users WHERE email=$1 AND id<>$2',[email,req.user.id]); if(exists.rowCount) return res.status(409).json({error:'Diese E-Mail-Adresse wird bereits verwendet.'});
    await pool.query('UPDATE users SET email=$2,email_verified_at=NULL WHERE id=$1',[req.user.id,email]);
    try{await issueVerification(req.user.id,email,req.user.name)}catch(e){console.error('Verification after email change failed',e)}
    res.json({ok:true,email,verificationMailSent:Boolean(mailer)});
  } catch(error){next(error)}
});

app.get('/api/account/export', auth, async (req,res,next)=>{
  try {
    const [user,cases,links,memberships]=await Promise.all([
      pool.query('SELECT id,name,email,street,postal_code,city,country,phone,email_verified_at,created_at FROM users WHERE id=$1',[req.user.id]),
      pool.query(`SELECT c.*, COALESCE(json_agg(DISTINCT jsonb_build_object('id',a.id,'name',a.original_name,'mimeType',a.mime_type,'size',a.size_bytes,'createdAt',a.created_at)) FILTER (WHERE a.id IS NOT NULL),'[]') attachments FROM defect_cases c LEFT JOIN attachments a ON a.case_id=c.id WHERE c.user_id=$1 GROUP BY c.id ORDER BY c.created_at`,[req.user.id]),
      pool.query(`SELECT tl.id,tl.status,tl.created_at,tl.disconnected_at,o.name organization,p.name property,u.label unit FROM tenant_links tl JOIN organizations o ON o.id=tl.organization_id JOIN properties p ON p.id=tl.property_id JOIN units u ON u.id=tl.unit_id WHERE tl.user_id=$1`,[req.user.id]),
      pool.query(`SELECT om.organization_id,o.name,om.role,COALESCE(om.active,true) active,om.created_at FROM organization_memberships om JOIN organizations o ON o.id=om.organization_id WHERE om.user_id=$1`,[req.user.id])
    ]);
    const payload={exportedAt:new Date().toISOString(),account:user.rows[0],cases:cases.rows,tenantLinks:links.rows,organizations:memberships.rows};
    res.setHeader('Content-Type','application/json; charset=utf-8'); res.setHeader('Content-Disposition','attachment; filename="maengelfix-datenexport.json"'); res.send(JSON.stringify(payload,null,2));
  } catch(error){next(error)}
});

app.post('/api/tenant-links/:linkId/disconnect', auth, async (req,res,next)=>{
  try {
    const r=await pool.query(`UPDATE tenant_links SET status='disconnected',disconnected_at=now(),disconnected_by=$2 WHERE id=$1 AND user_id=$2 AND status='active' RETURNING id`,[req.params.linkId,req.user.id]);
    if(!r.rowCount) return res.status(404).json({error:'Aktive Verknüpfung nicht gefunden.'}); res.json({ok:true});
  } catch(error){next(error)}
});

app.patch('/api/team/members/:userId/status', auth, async (req,res,next)=>{
  try {
    const org=await organizationForUser(req.user.id); if(!org||!['owner','admin'].includes(org.role)) return res.status(403).json({error:'Keine Berechtigung.'});
    if(req.params.userId===req.user.id) return res.status(400).json({error:'Deinen eigenen Zugang kannst du hier nicht deaktivieren.'});
    const target=await pool.query('SELECT role FROM organization_memberships WHERE organization_id=$1 AND user_id=$2',[org.id,req.params.userId]); if(!target.rowCount) return res.status(404).json({error:'Mitarbeiter nicht gefunden.'});
    if(target.rows[0].role==='owner') return res.status(400).json({error:'Der Inhaber kann nicht deaktiviert werden.'});
    const active=Boolean(req.body.active); await pool.query(`UPDATE organization_memberships SET active=$3,deactivated_at=CASE WHEN $3 THEN NULL ELSE now() END,deactivated_by=CASE WHEN $3 THEN NULL ELSE $4 END WHERE organization_id=$1 AND user_id=$2`,[org.id,req.params.userId,active,req.user.id]);
    if(!active) await pool.query('DELETE FROM sessions WHERE user_id=$1',[req.params.userId]); res.json({ok:true,active});
  } catch(error){next(error)}
});

app.post('/api/team/transfer-ownership', auth, async (req,res,next)=>{
  const client=await pool.connect(); try {
    const org=await organizationForUser(req.user.id); if(!org||org.role!=='owner') return res.status(403).json({error:'Nur der aktuelle Inhaber kann die Inhaberschaft übertragen.'});
    const targetId=cleanText(req.body.userId,80); const t=await client.query(`SELECT role,COALESCE(active,true) active FROM organization_memberships WHERE organization_id=$1 AND user_id=$2`,[org.id,targetId]); if(!t.rowCount||!t.rows[0].active) return res.status(400).json({error:'Bitte wähle einen aktiven Mitarbeiter.'});
    await client.query('BEGIN'); await client.query(`UPDATE organization_memberships SET role='admin' WHERE organization_id=$1 AND user_id=$2`,[org.id,req.user.id]); await client.query(`UPDATE organization_memberships SET role='owner' WHERE organization_id=$1 AND user_id=$2`,[org.id,targetId]); await client.query('COMMIT'); res.json({ok:true});
  } catch(error){await client.query('ROLLBACK');next(error)} finally{client.release()}
});

app.post('/api/team/leave', auth, async (req,res,next)=>{
  try {
    const org=await organizationForUser(req.user.id); if(!org) return res.status(404).json({error:'Du gehörst zu keinem Verwaltungs-Arbeitsbereich.'}); if(org.role==='owner') return res.status(400).json({error:'Übertrage zuerst die Inhaberschaft, bevor du die Organisation verlässt.'});
    await pool.query('DELETE FROM organization_memberships WHERE organization_id=$1 AND user_id=$2',[org.id,req.user.id]); res.json({ok:true});
  } catch(error){next(error)}
});

app.delete('/api/account', auth, async (req,res,next)=>{
  const client=await pool.connect(); try {
    const password=String(req.body.password||''); const confirmation=String(req.body.confirmation||''); if(confirmation!=='LÖSCHEN') return res.status(400).json({error:'Bitte gib zur Bestätigung LÖSCHEN ein.'});
    const u=await client.query('SELECT password_salt,password_hash FROM users WHERE id=$1',[req.user.id]); if(!(await verifyPassword(password,u.rows[0].password_salt,u.rows[0].password_hash))) return res.status(401).json({error:'Das Passwort ist nicht korrekt.'});
    const owned=await client.query(`SELECT o.id,o.name FROM organizations o JOIN organization_memberships om ON om.organization_id=o.id WHERE om.user_id=$1 AND om.role='owner' AND COALESCE(om.active,true)=true`,[req.user.id]); if(owned.rowCount) return res.status(409).json({error:`Du bist noch Inhaber von „${owned.rows[0].name}“. Übertrage zuerst die Inhaberschaft.`});
    await client.query('BEGIN'); await client.query('DELETE FROM users WHERE id=$1',[req.user.id]); await client.query('COMMIT'); res.clearCookie(cookieName,{path:'/'}); res.json({ok:true});
  } catch(error){await client.query('ROLLBACK');next(error)} finally{client.release()}
});

'''
    server=server.replace(anchor,endpoints+anchor)
server_p.write_text(server)

# Add AccountSecurityView before TeamView.
if 'function AccountSecurityView' not in app:
    comp=r'''
function AccountSecurityView({ user, onUserChanged, onSignedOut }) {
  const [team,setTeam]=useState(null); const [links,setLinks]=useState([]); const [msg,setMsg]=useState(''); const [error,setError]=useState('');
  const [pw,setPw]=useState({currentPassword:'',newPassword:''}); const [email,setEmail]=useState({email:user.email,password:''}); const [del,setDel]=useState({password:'',confirmation:''});
  async function load(){try{const [t,l]=await Promise.all([api('/api/team'),api('/api/tenant-links').catch(()=>({links:[]}))]);setTeam(t);setLinks(l.links||l||[])}catch(e){setError(e.message)}} useEffect(()=>{load()},[]);
  async function changePassword(e){e.preventDefault();setError('');try{await api('/api/account/change-password',{method:'POST',body:JSON.stringify(pw)});setPw({currentPassword:'',newPassword:''});setMsg('Passwort wurde geändert.')}catch(e){setError(e.message)}}
  async function changeEmail(e){e.preventDefault();setError('');try{const r=await api('/api/account/email',{method:'PATCH',body:JSON.stringify(email)});onUserChanged?.({...user,email:r.email,emailVerified:false});setEmail({email:r.email,password:''});setMsg(r.verificationMailSent?'Neue E-Mail gespeichert. Bitte bestätige sie über die E-Mail.':'Neue E-Mail gespeichert. SMTP ist noch nicht aktiv.')}catch(e){setError(e.message)}}
  async function disconnect(id){if(!confirm('Diese Verbindung zur Hausverwaltung wirklich trennen?'))return;try{await api(`/api/tenant-links/${id}/disconnect`,{method:'POST'});setMsg('Verknüpfung wurde getrennt.');await load()}catch(e){setError(e.message)}}
  async function leave(){if(!confirm('Verwaltungs-Arbeitsbereich wirklich verlassen?'))return;try{await api('/api/team/leave',{method:'POST'});setMsg('Arbeitsbereich verlassen.');await load()}catch(e){setError(e.message)}}
  async function removeAccount(e){e.preventDefault();if(!confirm('Das Konto und deine persönlichen Daten dauerhaft löschen? Dieser Schritt kann nicht rückgängig gemacht werden.'))return;try{await api('/api/account',{method:'DELETE',body:JSON.stringify(del)});onSignedOut?.()}catch(e){setError(e.message)}}
  return <div className="workspacePage accountSecurity"><div className="workspaceHeading"><div><span>KONTO & DATENSCHUTZ</span><h1>Sicherheit und deine Daten</h1><p>Login, Verknüpfungen, Datenexport und Kontolöschung an einem Ort.</p></div></div>{msg&&<div className="successBox">{msg}</div>}{error&&<div className="errorBox">{error}</div>}<div className="settingsGrid"><section className="workspacePanel"><h2>Passwort ändern</h2><form className="formStack" onSubmit={changePassword}><label>Aktuelles Passwort<input type="password" required value={pw.currentPassword} onChange={e=>setPw({...pw,currentPassword:e.target.value})}/></label><label>Neues Passwort<input type="password" minLength="8" required value={pw.newPassword} onChange={e=>setPw({...pw,newPassword:e.target.value})}/></label><button className="primaryButton">Passwort ändern</button></form></section><section className="workspacePanel"><h2>E-Mail-Adresse</h2><form className="formStack" onSubmit={changeEmail}><label>Neue E-Mail<input type="email" required value={email.email} onChange={e=>setEmail({...email,email:e.target.value})}/></label><label>Mit Passwort bestätigen<input type="password" required value={email.password} onChange={e=>setEmail({...email,password:e.target.value})}/></label><button className="primaryButton">E-Mail ändern</button></form></section></div><section className="workspacePanel privacyPanel"><h2>Deine Daten</h2><p>Lade eine strukturierte JSON-Kopie deiner Konto-, Vorgangs- und Verknüpfungsdaten herunter.</p><a className="secondaryButton linkButton" href="/api/account/export">Datenexport herunterladen</a></section><section className="workspacePanel"><h2>Mieter-Verknüpfungen</h2>{links.length?links.filter(l=>l.status==='active').map(l=><div className="securityRow" key={l.id}><div><b>{l.organization_name||l.organization}</b><span>{l.property_name||l.property} · {l.unit_label||l.unit}</span></div><button className="dangerGhost" onClick={()=>disconnect(l.id)}>Trennen</button></div>):<p className="muted">Keine aktiven Verknüpfungen.</p>}</section>{team?.organization&&<section className="workspacePanel"><h2>Verwaltungs-Arbeitsbereich</h2><p><b>{team.organization.name}</b> · Rolle: {team.organization.role}</p>{team.organization.role==='owner'?<p className="muted">Als Inhaber musst du die Inhaberschaft im Team-Bereich zuerst übertragen, bevor du den Arbeitsbereich verlassen kannst.</p>:<button className="dangerGhost" onClick={leave}>Arbeitsbereich verlassen</button>}</section>}<section className="workspacePanel dangerZone"><span>GEFAHRENZONE</span><h2>Konto dauerhaft löschen</h2><p>Persönliche Daten und private Vorgänge werden gelöscht. Bist du noch Inhaber einer Verwaltung, wird die Löschung blockiert.</p><form className="formStack" onSubmit={removeAccount}><label>Passwort<input type="password" required value={del.password} onChange={e=>setDel({...del,password:e.target.value})}/></label><label>Zur Bestätigung „LÖSCHEN“ eingeben<input required value={del.confirmation} onChange={e=>setDel({...del,confirmation:e.target.value})}/></label><button className="dangerButton">Konto endgültig löschen</button></form></section></div>;
}

'''
    marker='function TeamView('
    if marker in app: app=app.replace(marker,comp+marker,1)

# Wire view and navigation using stable strings.
app=app.replace("else if (view === 'team') content = <TeamView", "else if (view === 'security') content = <AccountSecurityView user={user} onUserChanged={setUser} onSignedOut={onSignedOut} />;\n  else if (view === 'team') content = <TeamView",1)
nav_anchor="<button className={view === 'team' ? 'active' : ''}"
if "view === 'security'" not in app and nav_anchor in app:
    app=app.replace(nav_anchor,"<button className={view === 'security' ? 'active' : ''} onClick={() => { setSelected(null); setView('security'); }}><span>⚙</span>Konto & Datenschutz</button>"+nav_anchor,1)
app_p.write_text(app)

if '/* v0.10 account security */' not in css:
    css += '''\n/* v0.10 account security */\n.settingsGrid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.privacyPanel{margin-top:18px}.securityRow{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:14px 0;border-bottom:1px solid #e3e7eb}.securityRow:last-child{border-bottom:0}.securityRow div{display:flex;flex-direction:column;gap:4px}.securityRow span{color:#6f7a86;font-size:13px}.dangerGhost,.dangerButton{border:1px solid #c94949;background:#fff;color:#a52e2e;border-radius:8px;padding:10px 14px;font-weight:700;cursor:pointer}.dangerButton{background:#a52e2e;color:#fff}.dangerZone{margin-top:18px;border:1px solid #efcaca}.dangerZone>span{font-size:11px;font-weight:800;letter-spacing:.12em;color:#a52e2e}.successBox{padding:14px 16px;background:#edf8f0;border:1px solid #badfc2;border-radius:10px;color:#245b30;margin-bottom:16px}@media(max-width:760px){.settingsGrid{grid-template-columns:1fr}.securityRow{align-items:flex-start;flex-direction:column}}\n'''
css_p.write_text(css)
print('v0.10 account/privacy patch prepared')
