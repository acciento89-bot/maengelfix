from pathlib import Path
import json,re
root=Path('.')
schema_p=root/'server/schema.sql'; server_p=root/'server/index.js'; app_p=root/'client/src/App.jsx'; css_p=root/'client/src/maengelfix-pro.css'; pkg_p=root/'server/package.json'
schema=schema_p.read_text(); server=server_p.read_text(); app=app_p.read_text(); css=css_p.read_text(); pkg=json.loads(pkg_p.read_text())

if '-- v0.11: Aufgaben, Wiedervorlagen und Eskalationen' not in schema:
    schema += r'''

-- v0.11: Aufgaben, Wiedervorlagen und Eskalationen
CREATE TABLE IF NOT EXISTS case_tasks (
  id text PRIMARY KEY,
  organization_id text REFERENCES organizations(id) ON DELETE CASCADE,
  case_id text NOT NULL REFERENCES defect_cases(id) ON DELETE CASCADE,
  created_by text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  assigned_user_id text REFERENCES users(id) ON DELETE SET NULL,
  title text NOT NULL,
  description text,
  priority text NOT NULL DEFAULT 'normal',
  status text NOT NULL DEFAULT 'open',
  due_at timestamptz,
  remind_at timestamptz,
  reminder_sent_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS case_tasks_org_idx ON case_tasks(organization_id,status,due_at);
CREATE INDEX IF NOT EXISTS case_tasks_assignee_idx ON case_tasks(assigned_user_id,status,due_at);
CREATE INDEX IF NOT EXISTS case_tasks_case_idx ON case_tasks(case_id,created_at DESC);
'''
schema_p.write_text(schema)
pkg['version']='0.11.0'; pkg_p.write_text(json.dumps(pkg,ensure_ascii=False,indent=2)+'\n')
server=re.sub(r"res\.json\(\{ ok: true, service: 'maengelfix', version: '[^']+'[^}]*\}\);","res.json({ ok: true, service: 'maengelfix', version: '0.11.0', mail: smtpConfigured ? 'smtp' : 'manual' });",server,count=1)

api_anchor="app.get('/api/notifications', auth, async (req,res,next)=>{"
if "app.get('/api/tasks'" not in server:
    endpoints=r'''
app.get('/api/tasks', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    const mine=String(req.query.mine||'')==='1';
    const params=[]; let where='';
    if(organization){params.push(organization.id);where='t.organization_id=$1';if(mine){params.push(req.user.id);where+=' AND t.assigned_user_id=$2';}}
    else {params.push(req.user.id);where='t.organization_id IS NULL AND (t.created_by=$1 OR t.assigned_user_id=$1)';}
    const result=await pool.query(`SELECT t.*,c.title AS case_title,c.property_label,u.name AS assigned_name,creator.name AS creator_name
      FROM case_tasks t JOIN defect_cases c ON c.id=t.case_id
      LEFT JOIN users u ON u.id=t.assigned_user_id LEFT JOIN users creator ON creator.id=t.created_by
      WHERE ${where} ORDER BY CASE t.status WHEN 'open' THEN 0 ELSE 1 END,CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,t.due_at NULLS LAST,t.created_at DESC`,params);
    const now=Date.now();
    res.json({tasks:result.rows.map(t=>({...t,overdue:t.status==='open'&&t.due_at&&new Date(t.due_at).getTime()<now})),organization:organization||null});
  } catch(error){next(error)}
});

app.get('/api/cases/:caseId/tasks', auth, async (req,res,next)=>{
  try {
    const accessible=await canAccessCase(req.user.id,req.params.caseId); if(!accessible) return res.status(404).json({error:'Vorgang nicht gefunden.'});
    const result=await pool.query(`SELECT t.*,u.name AS assigned_name FROM case_tasks t LEFT JOIN users u ON u.id=t.assigned_user_id WHERE t.case_id=$1 ORDER BY CASE t.status WHEN 'open' THEN 0 ELSE 1 END,t.due_at NULLS LAST,t.created_at DESC`,[req.params.caseId]);
    let members=[]; if(accessible.organization_id){const m=await pool.query(`SELECT u.id,u.name FROM organization_memberships om JOIN users u ON u.id=om.user_id WHERE om.organization_id=$1 AND COALESCE(om.active,true)=true ORDER BY u.name`,[accessible.organization_id]);members=m.rows;}
    res.json({tasks:result.rows,members,organizationId:accessible.organization_id||null});
  } catch(error){next(error)}
});

app.post('/api/cases/:caseId/tasks', auth, async (req,res,next)=>{
  try {
    const accessible=await canAccessCase(req.user.id,req.params.caseId); if(!accessible) return res.status(404).json({error:'Vorgang nicht gefunden.'});
    const title=cleanText(req.body.title,180); if(!title) return res.status(400).json({error:'Bitte gib einen Aufgabentitel an.'});
    const priority=['low','normal','high','urgent'].includes(req.body.priority)?req.body.priority:'normal';
    let assigned=req.body.assignedUserId||req.user.id;
    if(accessible.organization_id){const m=await pool.query(`SELECT 1 FROM organization_memberships WHERE organization_id=$1 AND user_id=$2 AND COALESCE(active,true)=true`,[accessible.organization_id,assigned]);if(!m.rowCount)return res.status(400).json({error:'Der gewählte Mitarbeiter gehört nicht aktiv zur Verwaltung.'});}
    else assigned=req.user.id;
    const taskId=id(); const result=await pool.query(`INSERT INTO case_tasks (id,organization_id,case_id,created_by,assigned_user_id,title,description,priority,due_at,remind_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING *`,[taskId,accessible.organization_id||null,req.params.caseId,req.user.id,assigned,title,cleanText(req.body.description,1200),priority,req.body.dueAt||null,req.body.remindAt||null]);
    if(accessible.organization_id){await writeAudit({organizationId:accessible.organization_id,userId:req.user.id,caseId:req.params.caseId,action:'task_created',entityType:'task',entityId:taskId,summary:`Aufgabe „${title}“ erstellt.`});if(assigned!==req.user.id)await createNotification({userId:assigned,organizationId:accessible.organization_id,caseId:req.params.caseId,type:'task',title:'Neue Aufgabe für dich',body:title,link:'/app?view=tasks'});}
    res.status(201).json({task:result.rows[0]});
  } catch(error){next(error)}
});

app.patch('/api/tasks/:taskId', auth, async (req,res,next)=>{
  try {
    const r=await pool.query(`SELECT t.*,c.user_id AS case_owner FROM case_tasks t JOIN defect_cases c ON c.id=t.case_id WHERE t.id=$1`,[req.params.taskId]); if(!r.rowCount)return res.status(404).json({error:'Aufgabe nicht gefunden.'}); const task=r.rows[0];
    if(task.organization_id){const org=await organizationForUser(req.user.id);if(!org||org.id!==task.organization_id)return res.status(403).json({error:'Kein Zugriff.'});}
    else if(task.created_by!==req.user.id&&task.assigned_user_id!==req.user.id&&task.case_owner!==req.user.id)return res.status(403).json({error:'Kein Zugriff.'});
    const status=req.body.status==='done'?'done':req.body.status==='open'?'open':task.status;
    let assigned=req.body.assignedUserId===undefined?task.assigned_user_id:(req.body.assignedUserId||null);
    if(task.organization_id&&assigned){const m=await pool.query(`SELECT 1 FROM organization_memberships WHERE organization_id=$1 AND user_id=$2 AND COALESCE(active,true)=true`,[task.organization_id,assigned]);if(!m.rowCount)return res.status(400).json({error:'Ungültiger Mitarbeiter.'});}
    const result=await pool.query(`UPDATE case_tasks SET title=COALESCE($2,title),description=COALESCE($3,description),priority=COALESCE($4,priority),assigned_user_id=$5,due_at=$6,remind_at=$7,status=$8,completed_at=CASE WHEN $8='done' THEN COALESCE(completed_at,now()) ELSE NULL END,reminder_sent_at=CASE WHEN remind_at IS DISTINCT FROM $7 THEN NULL ELSE reminder_sent_at END,updated_at=now() WHERE id=$1 RETURNING *`,[task.id,cleanText(req.body.title,180),req.body.description===undefined?task.description:cleanText(req.body.description,1200),['low','normal','high','urgent'].includes(req.body.priority)?req.body.priority:task.priority,assigned,req.body.dueAt===undefined?task.due_at:(req.body.dueAt||null),req.body.remindAt===undefined?task.remind_at:(req.body.remindAt||null),status]);
    if(task.organization_id)await writeAudit({organizationId:task.organization_id,userId:req.user.id,caseId:task.case_id,action:status==='done'?'task_completed':'task_updated',entityType:'task',entityId:task.id,summary:status==='done'?`Aufgabe „${task.title}“ erledigt.`:`Aufgabe „${task.title}“ aktualisiert.`});
    res.json({task:result.rows[0]});
  } catch(error){next(error)}
});
'''
    server=server.replace(api_anchor,endpoints+api_anchor)

# Reminder worker: only marks once, safe across regular server loop.
listen_anchor="app.listen(port, '0.0.0.0', () => {"
if 'async function processTaskReminders()' not in server:
    worker=r'''
async function processTaskReminders(){
  try{
    const due=await pool.query(`SELECT t.*,u.email,u.name,c.title AS case_title FROM case_tasks t LEFT JOIN users u ON u.id=t.assigned_user_id JOIN defect_cases c ON c.id=t.case_id WHERE t.status='open' AND t.remind_at IS NOT NULL AND t.remind_at<=now() AND t.reminder_sent_at IS NULL LIMIT 100`);
    for(const task of due.rows){
      if(task.assigned_user_id) await createNotification({userId:task.assigned_user_id,organizationId:task.organization_id,caseId:task.case_id,type:'task_reminder',title:'Wiedervorlage fällig',body:task.title,link:'/app?view=tasks'});
      if(mailer&&task.email) try{await sendAppMail({to:task.email,subject:'MängelFix Wiedervorlage',heading:'Eine Aufgabe ist fällig',text:`${task.title}\nVorgang: ${task.case_title}`,buttonLabel:'Aufgaben öffnen',buttonUrl:`${appOrigin}/app?view=tasks`});}catch(e){console.error('Task reminder mail failed',e)}
      await pool.query('UPDATE case_tasks SET reminder_sent_at=now() WHERE id=$1 AND reminder_sent_at IS NULL',[task.id]);
    }
  }catch(error){console.error('Task reminder worker failed',error)}
}
setTimeout(processTaskReminders,15000);
setInterval(processTaskReminders,15*60*1000);

'''
    server=server.replace(listen_anchor,worker+listen_anchor)
server_p.write_text(server)

# ---------- Client ----------
component_anchor='function TeamView() {'
if 'function TasksView(' not in app:
    components=r'''
const taskPriorityLabels={low:'Niedrig',normal:'Normal',high:'Hoch',urgent:'Dringend'};
function taskDate(value){return value?new Date(value).toLocaleString('de-DE',{dateStyle:'medium',timeStyle:'short'}):'—'}

function TasksView({ onSelect }){
 const [data,setData]=useState({tasks:[],organization:null});const [mine,setMine]=useState(true);const [error,setError]=useState('');
 async function load(){try{setData(await api(`/api/tasks${mine?'?mine=1':''}`))}catch(e){setError(e.message)}} useEffect(()=>{load()},[mine]);
 async function toggle(t){try{await api(`/api/tasks/${t.id}`,{method:'PATCH',body:JSON.stringify({status:t.status==='done'?'open':'done'})});await load()}catch(e){setError(e.message)}}
 const open=data.tasks.filter(t=>t.status==='open'),done=data.tasks.filter(t=>t.status==='done');
 return <div className="workspacePage"><div className="workspaceHeading"><div><span>AUFGABEN & WIEDERVORLAGEN</span><h1>{data.organization?'Arbeitssteuerung':'Meine Wiedervorlagen'}</h1><p>Fälligkeiten, Prioritäten und nächste Schritte zentral im Blick.</p></div>{data.organization&&<div className="taskScope"><button className={mine?'active':''} onClick={()=>setMine(true)}>Meine Aufgaben</button><button className={!mine?'active':''} onClick={()=>setMine(false)}>Alle Aufgaben</button></div>}</div>{error&&<div className="errorBox">{error}</div>}<div className="taskMetrics"><article><span>OFFEN</span><b>{open.length}</b></article><article className="danger"><span>ÜBERFÄLLIG</span><b>{open.filter(t=>t.overdue).length}</b></article><article><span>ERLEDIGT</span><b>{done.length}</b></article></div><div className="taskList">{data.tasks.length?data.tasks.map(t=><article key={t.id} className={`taskRow priority-${t.priority} ${t.overdue?'overdue':''} ${t.status==='done'?'done':''}`}><button className="taskCheck" onClick={()=>toggle(t)}>{t.status==='done'?'✓':''}</button><button className="taskBody" onClick={()=>onSelect(t.case_id)}><div><span>{taskPriorityLabels[t.priority]}</span>{t.overdue&&<strong>ÜBERFÄLLIG</strong>}<h3>{t.title}</h3><p>{t.case_title}{t.property_label?` · ${t.property_label}`:''}</p></div><div className="taskMeta"><small>Fällig</small><b>{taskDate(t.due_at)}</b>{t.assigned_name&&<em>{t.assigned_name}</em>}</div></button></article>):<div className="emptyCard workspaceEmpty">Noch keine Aufgaben vorhanden.</div>}</div></div>;
}

function CaseTasksPanel({caseId}){
 const [data,setData]=useState({tasks:[],members:[]});const [open,setOpen]=useState(false);const [error,setError]=useState('');const [form,setForm]=useState({title:'',description:'',priority:'normal',assignedUserId:'',dueAt:'',remindAt:''});
 async function load(){try{const d=await api(`/api/cases/${caseId}/tasks`);setData(d);if(d.organizationId&&d.members.length&&!form.assignedUserId)setForm(f=>({...f,assignedUserId:d.members[0].id}))}catch(e){setError(e.message)}} useEffect(()=>{load()},[caseId]);
 async function create(e){e.preventDefault();try{await api(`/api/cases/${caseId}/tasks`,{method:'POST',body:JSON.stringify(form)});setForm(f=>({...f,title:'',description:'',dueAt:'',remindAt:''}));setOpen(false);await load()}catch(e){setError(e.message)}}
 async function toggle(t){try{await api(`/api/tasks/${t.id}`,{method:'PATCH',body:JSON.stringify({status:t.status==='done'?'open':'done'})});await load()}catch(e){setError(e.message)}}
 return <section className="contentCard caseTasks"><div className="sectionTitle"><div><div className="cardKicker">AUFGABEN</div><h3>Nächste Schritte & Wiedervorlagen</h3><p className="muted">Lege fest, wer was bis wann erledigen soll.</p></div><button className="secondaryButton" onClick={()=>setOpen(!open)}>{open?'Schließen':'+ Aufgabe'}</button></div>{error&&<div className="errorBox">{error}</div>}{open&&<form className="taskCreate" onSubmit={create}><div className="formGrid two"><label>Aufgabe<input required value={form.title} onChange={e=>setForm({...form,title:e.target.value})} placeholder="z. B. Rückmeldung vom Handwerker prüfen"/></label><label>Priorität<select value={form.priority} onChange={e=>setForm({...form,priority:e.target.value})}>{Object.entries(taskPriorityLabels).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>{data.organizationId&&<label>Zuständig<select value={form.assignedUserId} onChange={e=>setForm({...form,assignedUserId:e.target.value})}>{data.members.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select></label>}<label>Fällig am<input type="datetime-local" value={form.dueAt} onChange={e=>setForm({...form,dueAt:e.target.value})}/></label><label>Wiedervorlage<input type="datetime-local" value={form.remindAt} onChange={e=>setForm({...form,remindAt:e.target.value})}/></label></div><label>Notiz<textarea rows="2" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></label><button className="primaryButton">Aufgabe anlegen</button></form>}<div className="caseTaskList">{data.tasks.length?data.tasks.map(t=><div className={`caseTask ${t.status==='done'?'done':''}`} key={t.id}><button onClick={()=>toggle(t)}>{t.status==='done'?'✓':''}</button><div><b>{t.title}</b><span>{taskPriorityLabels[t.priority]} · {t.assigned_name||'Ich'} · Fällig {taskDate(t.due_at)}</span></div></div>):<div className="emptyInline">Noch keine Aufgaben für diesen Vorgang.</div>}</div></section>;
}

'''
    app=app.replace(component_anchor,components+component_anchor)

# Insert tasks panel after assignment panel in case detail.
needle='<AssignmentPanel caseId={caseId} item={item} onChanged={async()=>{await load();onUpdated();}} />'
if needle in app and '<CaseTasksPanel caseId={caseId}/>' not in app:
    app=app.replace(needle,needle+'<CaseTasksPanel caseId={caseId}/>')

# Route TasksView into workspace.
app=app.replace("else if (view === 'notifications') content = <NotificationsView", "else if (view === 'tasks') content = <TasksView onSelect={setSelected} />;\n  else if (view === 'notifications') content = <NotificationsView")
# Sidebar before notifications (fallback: before team).
notif='<button className={view === \'notifications\' ? \'active\' : \'\'} onClick={() => { setSelected(null); setView(\'notifications\'); }}><span>B</span>Benachrichtigungen {unreadNotifications>0&&<b>{unreadNotifications}</b>}</button>'
if notif in app and "setView('tasks')" not in app:
    app=app.replace(notif,"<button className={view === 'tasks' ? 'active' : ''} onClick={() => { setSelected(null); setView('tasks'); }}><span>✓</span>Aufgaben</button>"+notif)
app_p.write_text(app)

css += r'''
/* v0.11 Aufgaben & Wiedervorlagen */
.taskScope{display:flex;gap:6px;background:#eef1f3;padding:5px;border-radius:10px}.taskScope button{border:0;background:transparent;padding:9px 14px;border-radius:7px;font-weight:700}.taskScope button.active{background:#18212b;color:#fff}.taskMetrics{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:18px 0}.taskMetrics article{background:#fff;border:1px solid #dce2e5;border-radius:12px;padding:18px}.taskMetrics span{display:block;font-size:11px;font-weight:800;letter-spacing:.1em;color:#78838d}.taskMetrics b{display:block;font-size:28px;margin-top:5px}.taskMetrics .danger b{color:#b42318}.taskList{display:grid;gap:9px}.taskRow{display:flex;background:#fff;border:1px solid #dce2e5;border-left:5px solid #89939c;border-radius:11px;overflow:hidden}.taskRow.priority-high{border-left-color:#e18b24}.taskRow.priority-urgent,.taskRow.overdue{border-left-color:#c83d32}.taskRow.done{opacity:.58}.taskCheck{width:52px;border:0;border-right:1px solid #e4e8ea;background:#fafbfb;font-size:20px}.taskBody{border:0;background:transparent;display:flex;flex:1;justify-content:space-between;text-align:left;padding:15px 18px;gap:18px}.taskBody h3{margin:4px 0}.taskBody p{margin:0;color:#69747d}.taskBody span,.taskBody strong{font-size:10px;letter-spacing:.08em;font-weight:800;margin-right:8px}.taskBody strong{color:#b42318}.taskMeta{text-align:right;min-width:175px}.taskMeta small,.taskMeta em{display:block;color:#79838b;font-style:normal}.taskMeta b{display:block;margin:4px 0}.caseTasks{margin-top:18px}.taskCreate{padding:18px;background:#f5f7f7;border-radius:10px;margin:14px 0}.caseTaskList{display:grid;gap:8px}.caseTask{display:flex;gap:12px;align-items:center;border:1px solid #e0e5e7;padding:11px 13px;border-radius:9px}.caseTask>button{width:28px;height:28px;border:1px solid #aab4ba;border-radius:50%;background:#fff}.caseTask span{display:block;color:#74808a;font-size:12px;margin-top:3px}.caseTask.done{text-decoration:line-through;opacity:.55}@media(max-width:760px){.taskMetrics{grid-template-columns:1fr 1fr 1fr}.taskBody{flex-direction:column}.taskMeta{text-align:left}.taskScope{width:100%}}
'''
css_p.write_text(css)
print('v0.11 task upgrade prepared')
