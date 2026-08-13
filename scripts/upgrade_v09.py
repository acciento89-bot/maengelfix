from pathlib import Path
import json
import re

root=Path('.')
schema_path=root/'server/schema.sql'
server_path=root/'server/index.js'
app_path=root/'client/src/App.jsx'
css_path=root/'client/src/maengelfix-pro.css'
pkg_path=root/'server/package.json'

schema=schema_path.read_text()
server=server_path.read_text()
app=app_path.read_text()
css=css_path.read_text()
pkg=json.loads(pkg_path.read_text())

schema_block=r'''

-- v0.9: Benachrichtigungen, Audit-Log & Verwaltungsstatus
CREATE TABLE IF NOT EXISTS notifications (
  id text PRIMARY KEY,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  organization_id text REFERENCES organizations(id) ON DELETE CASCADE,
  case_id text REFERENCES defect_cases(id) ON DELETE CASCADE,
  type text NOT NULL,
  title text NOT NULL,
  body text,
  link text,
  read_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS notifications_user_idx ON notifications(user_id, read_at, created_at DESC);

CREATE TABLE IF NOT EXISTS audit_logs (
  id text PRIMARY KEY,
  organization_id text NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id text REFERENCES users(id) ON DELETE SET NULL,
  case_id text REFERENCES defect_cases(id) ON DELETE SET NULL,
  action text NOT NULL,
  entity_type text NOT NULL,
  entity_id text,
  summary text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_logs_org_idx ON audit_logs(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_logs_case_idx ON audit_logs(case_id, created_at DESC);
'''
if '-- v0.9: Benachrichtigungen, Audit-Log & Verwaltungsstatus' not in schema:
    schema += schema_block
schema_path.write_text(schema)

pkg['version']='0.9.0'
pkg_path.write_text(json.dumps(pkg,ensure_ascii=False,indent=2)+'\n')

# Health/version is normalized regardless of older accidental version text.
server=re.sub(r"res\.json\(\{ ok: true, service: 'maengelfix', version: '[^']+'([\s\S]*?)\}\);", "res.json({ ok: true, service: 'maengelfix', version: '0.9.0', mail: smtpConfigured ? 'smtp' : 'manual' });", server, count=1)
server=server.replace("const allowedStatuses = new Set(['draft', 'sent', 'reply', 'in_progress', 'resolved']);", "const allowedStatuses = new Set(['draft','sent','reply','received','reviewing','commissioned','scheduled','in_progress','resolved']);")

helper_anchor="async function canAccessCase(userId, caseId) {"
if 'async function createNotification(' not in server:
    helper=r'''
async function createNotification({ userId, organizationId=null, caseId=null, type, title, body=null, link=null }) {
  if (!userId) return;
  await pool.query(`INSERT INTO notifications (id,user_id,organization_id,case_id,type,title,body,link) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`,
    [id(),userId,organizationId,caseId,type,title,body,link]);
}

async function notifyOrganization(organizationId, payload, excludeUserId=null) {
  if (!organizationId) return;
  const members=await pool.query('SELECT user_id FROM organization_memberships WHERE organization_id=$1',[organizationId]);
  await Promise.all(members.rows.filter(x=>x.user_id!==excludeUserId).map(x=>createNotification({userId:x.user_id,organizationId,...payload})));
}

async function writeAudit({ organizationId, userId=null, caseId=null, action, entityType, entityId=null, summary, metadata={} }) {
  if (!organizationId) return;
  await pool.query(`INSERT INTO audit_logs (id,organization_id,user_id,case_id,action,entity_type,entity_id,summary,metadata) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb)`,
    [id(),organizationId,userId,caseId,action,entityType,entityId,summary,JSON.stringify(metadata||{})]);
}

'''
    server=server.replace(helper_anchor,helper+helper_anchor)

api_anchor="app.get('/api/management/overview', auth, async (req, res, next) => {"
if "app.get('/api/notifications'" not in server:
    endpoints=r'''
app.get('/api/notifications', auth, async (req,res,next)=>{
  try {
    const result=await pool.query(`SELECT * FROM notifications WHERE user_id=$1 ORDER BY created_at DESC LIMIT 100`,[req.user.id]);
    res.json({notifications:result.rows,unread:result.rows.filter(x=>!x.read_at).length});
  } catch(error){next(error);}
});

app.post('/api/notifications/read-all', auth, async (req,res,next)=>{
  try { await pool.query('UPDATE notifications SET read_at=COALESCE(read_at,now()) WHERE user_id=$1',[req.user.id]); res.json({ok:true}); }
  catch(error){next(error);}
});

app.post('/api/notifications/:notificationId/read', auth, async (req,res,next)=>{
  try {
    const result=await pool.query('UPDATE notifications SET read_at=COALESCE(read_at,now()) WHERE id=$1 AND user_id=$2 RETURNING *',[req.params.notificationId,req.user.id]);
    if(!result.rowCount) return res.status(404).json({error:'Benachrichtigung nicht gefunden.'});
    res.json({notification:result.rows[0]});
  } catch(error){next(error);}
});

app.get('/api/audit', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization) return res.status(403).json({error:'Das Aktivitätsprotokoll ist im Verwaltungsbereich verfügbar.'});
    const result=await pool.query(`SELECT al.*,u.name AS actor_name FROM audit_logs al LEFT JOIN users u ON u.id=al.user_id WHERE al.organization_id=$1 ORDER BY al.created_at DESC LIMIT 250`,[organization.id]);
    res.json({logs:result.rows});
  } catch(error){next(error);}
});

'''
    server=server.replace(api_anchor,endpoints+api_anchor)

# Digital tenant submissions: start as received and create management alerts/audit.
server=server.replace("Boolean(destination),\n        title,", "Boolean(destination),\n        title,")
server=server.replace("req.body.deadlineOn || null\n      ]\n    );", "req.body.deadlineOn || null\n      ]\n    );\n    if (destination) {\n      await client.query(`UPDATE defect_cases SET status='received' WHERE id=$1`,[caseId]);\n      result.rows[0].status='received';\n      await notifyOrganization(destination.organization_id,{caseId,type:'tenant_case',title:'Neue Mängelmeldung vom Mieter',body:title,link:`/app?case=${caseId}`},req.user.id);\n      await writeAudit({organizationId:destination.organization_id,userId:req.user.id,caseId,action:'tenant_submitted',entityType:'case',entityId:caseId,summary:`Mieter hat den Mangel „${title}“ digital übermittelt.`});\n    }",1)

# Status change audit + tenant notification.
old_status=r'''    if (nextStatus !== old.status) {
      await pool.query(
        'INSERT INTO case_events (id, case_id, user_id, event_type, note) VALUES ($1,$2,$3,$4,$5)',
        [id(), req.params.caseId, req.user.id, 'status', `Status geändert: ${nextStatus}`]
      );
    }
    res.json({ case: result.rows[0] });'''
new_status=r'''    if (nextStatus !== old.status) {
      await pool.query(
        'INSERT INTO case_events (id, case_id, user_id, event_type, note) VALUES ($1,$2,$3,$4,$5)',
        [id(), req.params.caseId, req.user.id, 'status', `Status geändert: ${nextStatus}`]
      );
      if (old.organization_id) {
        await writeAudit({organizationId:old.organization_id,userId:req.user.id,caseId:req.params.caseId,action:'status_changed',entityType:'case',entityId:req.params.caseId,summary:`Status von „${old.status}“ auf „${nextStatus}“ geändert.`,metadata:{from:old.status,to:nextStatus}});
        if (old.submitted_by_tenant && old.user_id !== req.user.id) {
          await createNotification({userId:old.user_id,organizationId:old.organization_id,caseId:req.params.caseId,type:'status',title:'Status deiner Mängelmeldung geändert',body:`${old.title}: ${nextStatus}`,link:`/app?case=${req.params.caseId}`});
        }
      }
    }
    res.json({ case: result.rows[0] });'''
if old_status in server:
    server=server.replace(old_status,new_status)

# Internal notes are auditable.
old_note="await pool.query('UPDATE defect_cases SET updated_at=now() WHERE id=$1', [req.params.caseId]);\n    res.status(201).json({ event: result.rows[0] });"
new_note="await pool.query('UPDATE defect_cases SET updated_at=now() WHERE id=$1', [req.params.caseId]);\n    if (accessible.organization_id) await writeAudit({organizationId:accessible.organization_id,userId:req.user.id,caseId:req.params.caseId,action:'note_added',entityType:'case',entityId:req.params.caseId,summary:'Interne Notiz zum Vorgang ergänzt.'});\n    res.status(201).json({ event: result.rows[0] });"
server=server.replace(old_note,new_note,1)

# Shared messages: notify opposite side and audit.
msg_anchor="res.status(201).json({message:inserted.rows[0]});"
if msg_anchor in server:
    server=server.replace(msg_anchor,"""if(accessible.organization_id){
      await writeAudit({organizationId:accessible.organization_id,userId:req.user.id,caseId:req.params.caseId,action:'message_sent',entityType:'case',entityId:req.params.caseId,summary:'Gemeinsame Nachricht im Vorgang gesendet.'});
      const org=await organizationForUser(req.user.id);
      if(org && accessible.user_id!==req.user.id) await createNotification({userId:accessible.user_id,organizationId:accessible.organization_id,caseId:req.params.caseId,type:'message',title:'Neue Nachricht der Hausverwaltung',body:message.slice(0,180),link:`/app?case=${req.params.caseId}`});
      else await notifyOrganization(accessible.organization_id,{caseId:req.params.caseId,type:'message',title:'Neue Nachricht vom Mieter',body:message.slice(0,180),link:`/app?case=${req.params.caseId}`},req.user.id);
    }
    res.status(201).json({message:inserted.rows[0]});""",1)

# Assignment audit.
assign_phrase="res.json({case:result.rows[0]});"
# first suitable occurrence after assignment endpoint only
idx=server.find("app.patch('/api/cases/:caseId/assignment'")
if idx!=-1:
    end=server.find("});",idx)
    segment=server[idx:server.find("\n});",idx)+4]
    if "assignment_changed" not in segment and assign_phrase in segment:
        segment=segment.replace(assign_phrase,"await writeAudit({organizationId:organization.id,userId:req.user.id,caseId:req.params.caseId,action:'assignment_changed',entityType:'case',entityId:req.params.caseId,summary:'Objekt-, Einheiten- oder Mitarbeiterzuordnung geändert.',metadata:{propertyId,unitId,assignedUserId}});\n    "+assign_phrase)
        server=server[:idx]+segment+server[idx+len(segment):]

# Work order creation audit + notification to org members.
wo_marker="await client.query(`INSERT INTO case_events (id,case_id,user_id,event_type,note,visibility) VALUES ($1,$2,$3,'note',$4,'internal')`,[id(),req.params.caseId,req.user.id,`Arbeitsauftrag an ${provider.company_name} erstellt${delivery==='email'?' und per E-Mail versendet':''}.`]);"
if wo_marker in server and "work_order_created" not in server[server.find(wo_marker):server.find(wo_marker)+900]:
    server=server.replace(wo_marker,wo_marker+"\n    await writeAudit({organizationId:organization.id,userId:req.user.id,caseId:req.params.caseId,action:'work_order_created',entityType:'work_order',entityId:orderId,summary:`Arbeitsauftrag an ${provider.company_name} erstellt.`});",1)

server_path.write_text(server)

# ---------- Client ----------
app=app.replace("const statusLabels = {\n  draft: 'Entwurf',\n  sent: 'Versendet',\n  reply: 'Rückmeldung',\n  in_progress: 'In Bearbeitung',\n  resolved: 'Erledigt'\n};", "const statusLabels = { draft:'Entwurf', sent:'Versendet', reply:'Rückmeldung', received:'Eingegangen', reviewing:'In Prüfung', commissioned:'Auftrag erstellt', scheduled:'Termin geplant', in_progress:'In Ausführung', resolved:'Erledigt' };\nconst managementStatusLabels = { received:'Eingegangen', reviewing:'In Prüfung', commissioned:'Auftrag erstellt', scheduled:'Termin geplant', in_progress:'In Ausführung', resolved:'Erledigt' };\nconst privateStatusLabels = { draft:'Entwurf', sent:'Versendet', reply:'Rückmeldung', in_progress:'In Bearbeitung', resolved:'Erledigt' };")

# Case status select uses role-sensitive labels.
app=app.replace("<select disabled={busy} value={item.status} onChange={e => changeStatus(e.target.value)}>{Object.entries(statusLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>", "<select disabled={busy} value={item.status} onChange={e => changeStatus(e.target.value)}>{Object.entries(data.viewerRole==='management'?managementStatusLabels:privateStatusLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select>")

# Add notification/audit components before TeamView.
component_anchor="function TeamView() {"
if 'function NotificationsView(' not in app:
    components=r'''
function NotificationsView({ onSelect, refreshUnread }) {
  const [data,setData]=useState({notifications:[],unread:0}); const [error,setError]=useState('');
  async function load(){try{setData(await api('/api/notifications'));refreshUnread?.();}catch(e){setError(e.message)}}
  useEffect(()=>{load()},[]);
  async function open(item){try{if(!item.read_at)await api(`/api/notifications/${item.id}/read`,{method:'POST'});if(item.case_id)onSelect(item.case_id);else if(item.link)window.location.href=item.link;else await load();refreshUnread?.();}catch(e){setError(e.message)}}
  async function readAll(){try{await api('/api/notifications/read-all',{method:'POST'});await load();refreshUnread?.();}catch(e){setError(e.message)}}
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>BENACHRICHTIGUNGEN</span><h1>Was deine Aufmerksamkeit braucht</h1><p>Mietermeldungen, Nachrichten, Statusänderungen und wichtige Vorgänge an einer Stelle.</p></div>{data.unread>0&&<button className="secondaryButton" onClick={readAll}>Alle als gelesen markieren</button>}</div>{error&&<div className="errorBox">{error}</div>}<div className="notificationList">{data.notifications.length?data.notifications.map(n=><button key={n.id} className={`notificationRow ${n.read_at?'':'unread'}`} onClick={()=>open(n)}><div className="notificationIcon">{n.type==='tenant_case'?'!':n.type==='message'?'✉':n.type==='status'?'↻':'•'}</div><div><span>{n.type.replace('_',' ').toUpperCase()}</span><h3>{n.title}</h3><p>{n.body||''}</p><small>{new Date(n.created_at).toLocaleString('de-DE')}</small></div>{!n.read_at&&<i/>}</button>):<div className="emptyCard workspaceEmpty">Keine Benachrichtigungen vorhanden.</div>}</div></div>;
}

function AuditView() {
  const [logs,setLogs]=useState([]); const [error,setError]=useState('');
  useEffect(()=>{api('/api/audit').then(d=>setLogs(d.logs||[])).catch(e=>setError(e.message))},[]);
  const labels={tenant_submitted:'Mietermeldung',status_changed:'Status',assignment_changed:'Zuordnung',note_added:'Interne Notiz',message_sent:'Nachricht',work_order_created:'Arbeitsauftrag'};
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>AKTIVITÄTSPROTOKOLL</span><h1>Wer hat was gemacht?</h1><p>Nachvollziehbare Historie wichtiger Aktionen im Verwaltungs-Arbeitsbereich.</p></div></div>{error&&<div className="errorBox">{error}</div>}<div className="auditList">{logs.length?logs.map(log=><article key={log.id} className="auditRow"><div className="auditTime"><b>{new Date(log.created_at).toLocaleDateString('de-DE')}</b><span>{new Date(log.created_at).toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'})}</span></div><div><span>{labels[log.action]||log.action}</span><h3>{log.summary}</h3><p>{log.actor_name?`Durch ${log.actor_name}`:'Automatischer Vorgang'}</p></div></article>):<div className="emptyCard workspaceEmpty">Noch keine protokollierten Verwaltungsaktionen.</div>}</div></div>;
}

'''
    app=app.replace(component_anchor,components+component_anchor)

# Workspace state + refresh notifications
app=app.replace("const [management,setManagement]=useState(undefined);", "const [management,setManagement]=useState(undefined);\n  const [unreadNotifications,setUnreadNotifications]=useState(0);\n  async function refreshUnread(){try{const d=await api('/api/notifications');setUnreadNotifications(d.unread||0);}catch{setUnreadNotifications(0)}}")
app=app.replace("useEffect(() => { loadCases(); api('/api/management/overview').then(setManagement).catch(()=>setManagement({organization:null}));", "useEffect(() => { loadCases(); refreshUnread(); api('/api/management/overview').then(setManagement).catch(()=>setManagement({organization:null}));")

# Route views in workspace
app=app.replace("else if (view === 'team') content = <TeamView />;\n  else content = <ProfileView", "else if (view === 'notifications') content = <NotificationsView onSelect={setSelected} refreshUnread={refreshUnread} />;\n  else if (view === 'audit') content = <AuditView />;\n  else if (view === 'team') content = <TeamView />;\n  else content = <ProfileView")

# Sidebar buttons before Team
sidebar_marker="<button className={view === 'team' ? 'active' : ''} onClick={() => { setSelected(null); setView('team'); }}><span>T</span>{management?.organization ? 'Team' : 'Verwaltung'}</button>"
sidebar_new="<button className={view === 'notifications' ? 'active' : ''} onClick={() => { setSelected(null); setView('notifications'); }}><span>B</span>Benachrichtigungen {unreadNotifications>0&&<b>{unreadNotifications}</b>}</button>{management?.organization&&<button className={view === 'audit' ? 'active' : ''} onClick={() => { setSelected(null); setView('audit'); }}><span>A</span>Aktivitätsprotokoll</button>}"+sidebar_marker
app=app.replace(sidebar_marker,sidebar_new)
app_path.write_text(app)

css_block=r'''

/* v0.9 – Benachrichtigungen & Audit */
.notificationList,.auditList{display:grid;gap:10px}.notificationRow{width:100%;display:grid;grid-template-columns:44px 1fr 10px;gap:14px;align-items:start;text-align:left;background:var(--panel,#fff);border:1px solid var(--line,#dfe4e8);padding:17px 18px;cursor:pointer}.notificationRow.unread{border-left:4px solid #2457d6;background:#f8faff}.notificationIcon{width:38px;height:38px;display:grid;place-items:center;background:#eef2f6;font-weight:800;border-radius:8px}.notificationRow h3,.auditRow h3{margin:3px 0 5px}.notificationRow p,.auditRow p{margin:0;color:#68737f}.notificationRow small{display:block;margin-top:6px;color:#8b949e}.notificationRow>i{width:8px;height:8px;background:#2457d6;border-radius:50%;margin-top:8px}.auditRow{display:grid;grid-template-columns:105px 1fr;gap:18px;padding:17px 19px;border:1px solid var(--line,#dfe4e8);background:var(--panel,#fff)}.auditTime{display:flex;flex-direction:column}.auditTime span{color:#7b858f;font-size:12px}.auditRow>div:last-child>span,.notificationRow>div:nth-child(2)>span{font-size:10px;font-weight:800;letter-spacing:.1em;color:#2457d6}@media(max-width:720px){.auditRow{grid-template-columns:1fr}.notificationRow{grid-template-columns:38px 1fr 8px}}
'''
if '/* v0.9 – Benachrichtigungen & Audit */' not in css:
    css += css_block
css_path.write_text(css)
