from pathlib import Path
import json,re
root=Path('.')
schema_p=root/'server/schema.sql'; server_p=root/'server/index.js'; app_p=root/'client/src/App.jsx'; css_p=root/'client/src/maengelfix-pro.css'; pkg_p=root/'server/package.json'
schema=schema_p.read_text(); server=server_p.read_text(); app=app_p.read_text(); css=css_p.read_text(); pkg=json.loads(pkg_p.read_text())

if '-- v0.12: Kalender und Terminplanung' not in schema:
    schema += r'''

-- v0.12: Kalender und Terminplanung
CREATE TABLE IF NOT EXISTS calendar_events (
  id text PRIMARY KEY,
  organization_id text REFERENCES organizations(id) ON DELETE CASCADE,
  case_id text REFERENCES defect_cases(id) ON DELETE CASCADE,
  property_id text REFERENCES properties(id) ON DELETE SET NULL,
  unit_id text REFERENCES units(id) ON DELETE SET NULL,
  created_by text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  assigned_user_id text REFERENCES users(id) ON DELETE SET NULL,
  event_type text NOT NULL DEFAULT 'internal',
  title text NOT NULL,
  notes text,
  starts_at timestamptz NOT NULL,
  ends_at timestamptz NOT NULL,
  status text NOT NULL DEFAULT 'planned',
  notify_tenant boolean NOT NULL DEFAULT false,
  reminder_at timestamptz,
  reminder_sent_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS calendar_events_org_idx ON calendar_events(organization_id,starts_at);
CREATE INDEX IF NOT EXISTS calendar_events_user_idx ON calendar_events(assigned_user_id,starts_at);
CREATE INDEX IF NOT EXISTS calendar_events_case_idx ON calendar_events(case_id,starts_at);
'''
schema_p.write_text(schema)
pkg['version']='0.12.0'; pkg_p.write_text(json.dumps(pkg,ensure_ascii=False,indent=2)+'\n')
server=re.sub(r"res\.json\(\{ ok: true, service: 'maengelfix', version: '[^']+'[^}]*\}\);","res.json({ ok: true, service: 'maengelfix', version: '0.12.0', mail: smtpConfigured ? 'smtp' : 'manual' });",server,count=1)

api_anchor="app.get('/api/tasks', auth, async (req,res,next)=>{"
if "app.get('/api/calendar'" not in server:
    endpoints=r'''
function calendarRange(req){
  const now=new Date(); const from=req.query.from?new Date(req.query.from):new Date(now.getFullYear(),now.getMonth(),1); const to=req.query.to?new Date(req.query.to):new Date(now.getFullYear(),now.getMonth()+1,1);
  return {from:isNaN(from.getTime())?new Date(now.getFullYear(),now.getMonth(),1):from,to:isNaN(to.getTime())?new Date(now.getFullYear(),now.getMonth()+1,1):to};
}

app.get('/api/calendar', auth, async (req,res,next)=>{
  try{
    const organization=await organizationForUser(req.user.id); const {from,to}=calendarRange(req); const mine=String(req.query.mine||'')==='1';
    let own,orders=[];
    if(organization){
      const params=[organization.id,from,to]; let extra=''; if(mine){params.push(req.user.id);extra=' AND ce.assigned_user_id=$4';}
      own=(await pool.query(`SELECT ce.*,c.title AS case_title,p.name AS property_name,u.label AS unit_label,usr.name AS assigned_name FROM calendar_events ce LEFT JOIN defect_cases c ON c.id=ce.case_id LEFT JOIN properties p ON p.id=ce.property_id LEFT JOIN units u ON u.id=ce.unit_id LEFT JOIN users usr ON usr.id=ce.assigned_user_id WHERE ce.organization_id=$1 AND ce.starts_at<$3 AND ce.ends_at>$2${extra} ORDER BY ce.starts_at`,params)).rows;
      orders=(await pool.query(`SELECT wo.id,wo.case_id,wo.scheduled_for,wo.title,wo.status,sp.company_name,c.property_label,c.location_label,p.name AS property_name,u.label AS unit_label FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id JOIN defect_cases c ON c.id=wo.case_id LEFT JOIN properties p ON p.id=c.property_id LEFT JOIN units u ON u.id=c.unit_id WHERE wo.organization_id=$1 AND wo.scheduled_for IS NOT NULL AND wo.scheduled_for>=$2 AND wo.scheduled_for<$3 ORDER BY wo.scheduled_for`,[organization.id,from,to])).rows.map(x=>({id:`workorder:${x.id}`,case_id:x.case_id,title:`${x.company_name}: ${x.title}`,event_type:'contractor',status:x.status,starts_at:x.scheduled_for,ends_at:new Date(new Date(x.scheduled_for).getTime()+90*60000).toISOString(),property_name:x.property_name||x.property_label,unit_label:x.unit_label||x.location_label,assigned_name:x.company_name,readonly:true,source:'work_order'}));
    }else{
      own=(await pool.query(`SELECT ce.*,c.title AS case_title FROM calendar_events ce LEFT JOIN defect_cases c ON c.id=ce.case_id WHERE ce.organization_id IS NULL AND ce.created_by=$1 AND ce.starts_at<$3 AND ce.ends_at>$2 ORDER BY ce.starts_at`,[req.user.id,from,to])).rows;
    }
    res.json({events:[...own,...orders].sort((a,b)=>new Date(a.starts_at)-new Date(b.starts_at)),organization:organization||null});
  }catch(error){next(error)}
});

app.get('/api/cases/:caseId/calendar', auth, async (req,res,next)=>{
  try{
    const accessible=await canAccessCase(req.user.id,req.params.caseId); if(!accessible)return res.status(404).json({error:'Vorgang nicht gefunden.'});
    const events=(await pool.query(`SELECT ce.*,u.name AS assigned_name FROM calendar_events ce LEFT JOIN users u ON u.id=ce.assigned_user_id WHERE ce.case_id=$1 ORDER BY ce.starts_at`,[req.params.caseId])).rows;
    const orders=(await pool.query(`SELECT wo.id,wo.title,wo.status,wo.scheduled_for,sp.company_name FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id WHERE wo.case_id=$1 AND wo.scheduled_for IS NOT NULL ORDER BY wo.scheduled_for`,[req.params.caseId])).rows.map(x=>({id:`workorder:${x.id}`,title:`${x.company_name}: ${x.title}`,event_type:'contractor',status:x.status,starts_at:x.scheduled_for,ends_at:new Date(new Date(x.scheduled_for).getTime()+90*60000).toISOString(),assigned_name:x.company_name,readonly:true}));
    let members=[]; if(accessible.organization_id){members=(await pool.query(`SELECT u.id,u.name FROM organization_memberships om JOIN users u ON u.id=om.user_id WHERE om.organization_id=$1 AND COALESCE(om.active,true)=true ORDER BY u.name`,[accessible.organization_id])).rows;}
    res.json({events:[...events,...orders].sort((a,b)=>new Date(a.starts_at)-new Date(b.starts_at)),members,organizationId:accessible.organization_id||null,tenantVisible:Boolean(accessible.submitted_by_tenant)});
  }catch(error){next(error)}
});

app.post('/api/cases/:caseId/calendar', auth, async (req,res,next)=>{
  try{
    const accessible=await canAccessCase(req.user.id,req.params.caseId); if(!accessible)return res.status(404).json({error:'Vorgang nicht gefunden.'});
    const title=cleanText(req.body.title,180); const starts=new Date(req.body.startsAt); const ends=new Date(req.body.endsAt); if(!title||isNaN(starts.getTime())||isNaN(ends.getTime())||ends<=starts)return res.status(400).json({error:'Titel sowie gültiger Start und Ende sind erforderlich.'});
    const eventType=['internal','tenant','inspection'].includes(req.body.eventType)?req.body.eventType:'internal'; let assigned=req.body.assignedUserId||req.user.id;
    if(accessible.organization_id){const m=await pool.query(`SELECT 1 FROM organization_memberships WHERE organization_id=$1 AND user_id=$2 AND COALESCE(active,true)=true`,[accessible.organization_id,assigned]);if(!m.rowCount)return res.status(400).json({error:'Ungültiger Mitarbeiter.'});}else assigned=req.user.id;
    const notifyTenant=Boolean(req.body.notifyTenant&&accessible.organization_id&&accessible.submitted_by_tenant);
    const eventId=id(); const result=await pool.query(`INSERT INTO calendar_events (id,organization_id,case_id,property_id,unit_id,created_by,assigned_user_id,event_type,title,notes,starts_at,ends_at,status,notify_tenant,reminder_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,'planned',$13,$14) RETURNING *`,[eventId,accessible.organization_id||null,req.params.caseId,accessible.property_id||null,accessible.unit_id||null,req.user.id,assigned,eventType,title,cleanText(req.body.notes,2000),starts,ends,notifyTenant,req.body.reminderAt||null]);
    if(accessible.organization_id){await writeAudit({organizationId:accessible.organization_id,userId:req.user.id,caseId:req.params.caseId,action:'calendar_event_created',entityType:'calendar_event',entityId:eventId,summary:`Termin „${title}“ angelegt.`});if(assigned!==req.user.id)await createNotification({userId:assigned,organizationId:accessible.organization_id,caseId:req.params.caseId,type:'appointment',title:'Neuer Termin für dich',body:`${title} · ${starts.toLocaleString('de-DE')}`,link:'/app?view=calendar'});}
    if(notifyTenant){const owner=await tenantOwnerForCase(req.params.caseId);if(owner){await createNotification({userId:owner.id,organizationId:accessible.organization_id,caseId:req.params.caseId,type:'appointment',title:'Neuer Termin zu deiner Mängelmeldung',body:`${title} · ${starts.toLocaleString('de-DE')}`,link:`/app?case=${req.params.caseId}`});if(mailer)try{await sendAppMail({to:owner.email,subject:`Termin zu: ${accessible.title}`,heading:'Neuer Termin',text:`${title}\n${starts.toLocaleString('de-DE')} – ${ends.toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'})}`,buttonLabel:'Vorgang öffnen',buttonUrl:`${appOrigin}/app?case=${req.params.caseId}`})}catch(e){console.error('Appointment tenant mail failed',e)}}}
    res.status(201).json({event:result.rows[0]});
  }catch(error){next(error)}
});

app.patch('/api/calendar/:eventId', auth, async (req,res,next)=>{
  try{
    const r=await pool.query('SELECT * FROM calendar_events WHERE id=$1',[req.params.eventId]);if(!r.rowCount)return res.status(404).json({error:'Termin nicht gefunden.'});const ev=r.rows[0];
    if(ev.organization_id){const org=await organizationForUser(req.user.id);if(!org||org.id!==ev.organization_id)return res.status(403).json({error:'Kein Zugriff.'});}else if(ev.created_by!==req.user.id)return res.status(403).json({error:'Kein Zugriff.'});
    const status=['planned','confirmed','completed','cancelled'].includes(req.body.status)?req.body.status:ev.status; const starts=req.body.startsAt?new Date(req.body.startsAt):new Date(ev.starts_at); const ends=req.body.endsAt?new Date(req.body.endsAt):new Date(ev.ends_at); if(isNaN(starts)||isNaN(ends)||ends<=starts)return res.status(400).json({error:'Ungültiger Zeitraum.'});
    let assigned=req.body.assignedUserId===undefined?ev.assigned_user_id:(req.body.assignedUserId||null);if(ev.organization_id&&assigned){const m=await pool.query(`SELECT 1 FROM organization_memberships WHERE organization_id=$1 AND user_id=$2 AND COALESCE(active,true)=true`,[ev.organization_id,assigned]);if(!m.rowCount)return res.status(400).json({error:'Ungültiger Mitarbeiter.'});}
    const result=await pool.query(`UPDATE calendar_events SET title=$2,notes=$3,starts_at=$4,ends_at=$5,status=$6,assigned_user_id=$7,reminder_at=$8,reminder_sent_at=CASE WHEN reminder_at IS DISTINCT FROM $8 THEN NULL ELSE reminder_sent_at END,completed_at=CASE WHEN $6='completed' THEN COALESCE(completed_at,now()) ELSE NULL END,updated_at=now() WHERE id=$1 RETURNING *`,[ev.id,cleanText(req.body.title??ev.title,180),cleanText(req.body.notes??ev.notes,2000),starts,ends,status,assigned,req.body.reminderAt===undefined?ev.reminder_at:(req.body.reminderAt||null)]);
    if(ev.organization_id)await writeAudit({organizationId:ev.organization_id,userId:req.user.id,caseId:ev.case_id,action:'calendar_event_updated',entityType:'calendar_event',entityId:ev.id,summary:`Termin „${ev.title}“ aktualisiert.`});res.json({event:result.rows[0]});
  }catch(error){next(error)}
});

app.delete('/api/calendar/:eventId', auth, async (req,res,next)=>{
  try{const r=await pool.query('SELECT * FROM calendar_events WHERE id=$1',[req.params.eventId]);if(!r.rowCount)return res.status(404).json({error:'Termin nicht gefunden.'});const ev=r.rows[0];if(ev.organization_id){const org=await organizationForUser(req.user.id);if(!org||org.id!==ev.organization_id)return res.status(403).json({error:'Kein Zugriff.'});}else if(ev.created_by!==req.user.id)return res.status(403).json({error:'Kein Zugriff.'});await pool.query('DELETE FROM calendar_events WHERE id=$1',[ev.id]);if(ev.organization_id)await writeAudit({organizationId:ev.organization_id,userId:req.user.id,caseId:ev.case_id,action:'calendar_event_deleted',entityType:'calendar_event',entityId:ev.id,summary:`Termin „${ev.title}“ gelöscht.`});res.status(204).end();}catch(error){next(error)}
});
'''
    server=server.replace(api_anchor,endpoints+api_anchor)

listen_anchor="app.listen(port, '0.0.0.0', () => {"
if 'async function processCalendarReminders()' not in server:
    worker=r'''
async function processCalendarReminders(){
  try{const due=await pool.query(`SELECT ce.*,u.email,c.title AS case_title FROM calendar_events ce LEFT JOIN users u ON u.id=ce.assigned_user_id LEFT JOIN defect_cases c ON c.id=ce.case_id WHERE ce.status IN ('planned','confirmed') AND ce.reminder_at IS NOT NULL AND ce.reminder_at<=now() AND ce.reminder_sent_at IS NULL LIMIT 100`);for(const ev of due.rows){if(ev.assigned_user_id)await createNotification({userId:ev.assigned_user_id,organizationId:ev.organization_id,caseId:ev.case_id,type:'appointment_reminder',title:'Termin-Erinnerung',body:`${ev.title} · ${new Date(ev.starts_at).toLocaleString('de-DE')}`,link:'/app?view=calendar'});if(mailer&&ev.email)try{await sendAppMail({to:ev.email,subject:'MängelFix Termin-Erinnerung',heading:'Termin steht an',text:`${ev.title}\n${new Date(ev.starts_at).toLocaleString('de-DE')}${ev.case_title?`\nVorgang: ${ev.case_title}`:''}`,buttonLabel:'Kalender öffnen',buttonUrl:`${appOrigin}/app?view=calendar`})}catch(e){console.error('Calendar reminder mail failed',e)}await pool.query('UPDATE calendar_events SET reminder_sent_at=now() WHERE id=$1 AND reminder_sent_at IS NULL',[ev.id]);}}catch(error){console.error('Calendar reminder worker failed',error)}}
setTimeout(processCalendarReminders,20000);setInterval(processCalendarReminders,15*60*1000);

'''
    server=server.replace(listen_anchor,worker+listen_anchor)
server_p.write_text(server)

# ---------- Client ----------
component_anchor="const taskPriorityLabels={"
if 'function CalendarView(' not in app:
    components=r'''
const calendarTypeLabels={internal:'Intern',tenant:'Mietertermin',inspection:'Besichtigung / Prüfung',contractor:'Handwerker'};
function calDate(v){return v?new Date(v).toLocaleString('de-DE',{dateStyle:'medium',timeStyle:'short'}):'—'}
function dayKey(v){const d=new Date(v);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`}
function CalendarView({onSelect}){
 const [cursor,setCursor]=useState(()=>new Date());const [mine,setMine]=useState(false);const [data,setData]=useState({events:[],organization:null});const [error,setError]=useState('');
 const from=new Date(cursor.getFullYear(),cursor.getMonth(),1),to=new Date(cursor.getFullYear(),cursor.getMonth()+1,1);async function load(){try{setData(await api(`/api/calendar?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}${mine?'&mine=1':''}`))}catch(e){setError(e.message)}}useEffect(()=>{load()},[cursor,mine]);
 const days=[];const first=new Date(from);const pad=(first.getDay()+6)%7;for(let i=0;i<pad;i++)days.push(null);for(let d=new Date(from);d<to;d=new Date(d.getFullYear(),d.getMonth(),d.getDate()+1))days.push(new Date(d));
 return <div className="workspacePage calendarPage"><div className="workspaceHeading"><div><span>KALENDER & TERMINE</span><h1>{from.toLocaleDateString('de-DE',{month:'long',year:'numeric'})}</h1><p>Interne Termine, Mietertermine und bestätigte Handwerkertermine in einer Ansicht.</p></div><div className="calendarHeadActions"><button className="secondaryButton" onClick={()=>setCursor(new Date(cursor.getFullYear(),cursor.getMonth()-1,1))}>←</button><button className="secondaryButton" onClick={()=>setCursor(new Date())}>Heute</button><button className="secondaryButton" onClick={()=>setCursor(new Date(cursor.getFullYear(),cursor.getMonth()+1,1))}>→</button>{data.organization&&<button className={`secondaryButton ${mine?'active':''}`} onClick={()=>setMine(!mine)}>{mine?'Meine Termine':'Alle Termine'}</button>}</div></div>{error&&<div className="errorBox">{error}</div>}<div className="calendarWeekdays">{['Mo','Di','Mi','Do','Fr','Sa','So'].map(x=><b key={x}>{x}</b>)}</div><div className="calendarGrid">{days.map((day,i)=>day?<div className={`calendarDay ${dayKey(day)===dayKey(new Date())?'today':''}`} key={day.toISOString()}><strong>{day.getDate()}</strong><div>{data.events.filter(e=>dayKey(e.starts_at)===dayKey(day)).map(e=><button key={e.id} className={`calendarEvent type-${e.event_type}`} onClick={()=>e.case_id&&onSelect(e.case_id)} title={`${e.title} · ${calDate(e.starts_at)}`}><span>{new Date(e.starts_at).toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'})}</span><b>{e.title}</b><small>{calendarTypeLabels[e.event_type]||e.event_type}</small></button>)}</div></div>:<div className="calendarDay empty" key={`e${i}`}/>)}</div><section className="workspacePanel calendarAgenda"><div className="panelHead"><div><span>MONATSAGENDA</span><h2>{data.events.length} Termin{data.events.length===1?'':'e'}</h2></div></div>{data.events.length?data.events.map(e=><button className="agendaRow" key={e.id} onClick={()=>e.case_id&&onSelect(e.case_id)}><div className={`agendaMark type-${e.event_type}`}/><div><span>{calendarTypeLabels[e.event_type]||e.event_type}</span><h3>{e.title}</h3><p>{[e.property_name,e.unit_label,e.case_title,e.assigned_name].filter(Boolean).join(' · ')}</p></div><strong>{calDate(e.starts_at)}</strong></button>):<div className="emptyMini">Keine Termine in diesem Monat.</div>}</section></div>;
}

function CaseCalendarPanel({caseId}){
 const [data,setData]=useState({events:[],members:[],organizationId:null});const [open,setOpen]=useState(false);const [error,setError]=useState('');const [form,setForm]=useState({title:'',eventType:'internal',startsAt:'',endsAt:'',assignedUserId:'',reminderAt:'',notes:'',notifyTenant:false});
 async function load(){try{const d=await api(`/api/cases/${caseId}/calendar`);setData(d);if(d.organizationId&&d.members.length&&!form.assignedUserId)setForm(f=>({...f,assignedUserId:d.members[0].id}))}catch(e){setError(e.message)}}useEffect(()=>{load()},[caseId]);
 async function create(e){e.preventDefault();try{await api(`/api/cases/${caseId}/calendar`,{method:'POST',body:JSON.stringify(form)});setForm(f=>({...f,title:'',startsAt:'',endsAt:'',reminderAt:'',notes:'',notifyTenant:false}));setOpen(false);await load()}catch(e){setError(e.message)}}
 async function setStatus(ev,status){if(ev.readonly)return;try{await api(`/api/calendar/${ev.id}`,{method:'PATCH',body:JSON.stringify({status})});await load()}catch(e){setError(e.message)}}
 return <section className="contentCard caseCalendar"><div className="sectionTitle"><div><div className="cardKicker">TERMINE</div><h3>Kalender & Terminabsprachen</h3><p className="muted">Interne, Mieter- und Handwerkertermine direkt am Vorgang.</p></div><button className="secondaryButton" onClick={()=>setOpen(!open)}>{open?'Schließen':'+ Termin'}</button></div>{error&&<div className="errorBox">{error}</div>}{open&&<form className="calendarCreate" onSubmit={create}><div className="formGrid two"><label>Titel<input required value={form.title} onChange={e=>setForm({...form,title:e.target.value})} placeholder="z. B. Vor-Ort-Termin"/></label><label>Art<select value={form.eventType} onChange={e=>setForm({...form,eventType:e.target.value})}><option value="internal">Intern</option><option value="tenant">Mietertermin</option><option value="inspection">Besichtigung / Prüfung</option></select></label><label>Beginn<input type="datetime-local" required value={form.startsAt} onChange={e=>setForm({...form,startsAt:e.target.value})}/></label><label>Ende<input type="datetime-local" required value={form.endsAt} onChange={e=>setForm({...form,endsAt:e.target.value})}/></label>{data.organizationId&&<label>Zuständig<select value={form.assignedUserId} onChange={e=>setForm({...form,assignedUserId:e.target.value})}>{data.members.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select></label>}<label>Erinnerung<input type="datetime-local" value={form.reminderAt} onChange={e=>setForm({...form,reminderAt:e.target.value})}/></label></div><label>Notiz<textarea rows="2" value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></label>{data.tenantVisible&&<label className="tenantSubmissionToggle"><input type="checkbox" checked={form.notifyTenant} onChange={e=>setForm({...form,notifyTenant:e.target.checked})}/><span>Mieter über diesen Termin informieren</span></label>}<button className="primaryButton">Termin anlegen</button></form>}<div className="caseCalendarList">{data.events.length?data.events.map(ev=><article className={`caseCalendarItem type-${ev.event_type}`} key={ev.id}><div><span>{calendarTypeLabels[ev.event_type]||ev.event_type}</span><b>{ev.title}</b><small>{calDate(ev.starts_at)}{ev.assigned_name?` · ${ev.assigned_name}`:''}</small></div>{ev.readonly?<strong>{ev.status==='scheduled'?'BESTÄTIGT':'HANDWERKER'}</strong>:<select value={ev.status} onChange={e=>setStatus(ev,e.target.value)}><option value="planned">Geplant</option><option value="confirmed">Bestätigt</option><option value="completed">Erledigt</option><option value="cancelled">Abgesagt</option></select>}</article>):<div className="emptyInline">Noch keine Termine zu diesem Vorgang.</div>}</div></section>;
}

'''
    app=app.replace(component_anchor,components+component_anchor)
app=app.replace("<AssignmentPanel caseId={caseId} item={item} onChanged={async()=>{await load();onUpdated();}} /><CaseTasksPanel caseId={caseId}/>","<AssignmentPanel caseId={caseId} item={item} onChanged={async()=>{await load();onUpdated();}} /><CaseCalendarPanel caseId={caseId}/><CaseTasksPanel caseId={caseId}/>")
app=app.replace("else if (view === 'tasks') content = <TasksView onSelect={setSelected} />;","else if (view === 'calendar') content = <CalendarView onSelect={setSelected} />;\n  else if (view === 'tasks') content = <TasksView onSelect={setSelected} />;")
app=app.replace("<button className={view === 'tasks' ? 'active' : ''} onClick={() => { setSelected(null); setView('tasks'); }}><span>✓</span>Aufgaben</button>","<button className={view === 'calendar' ? 'active' : ''} onClick={() => { setSelected(null); setView('calendar'); }}><span>K</span>Kalender</button><button className={view === 'tasks' ? 'active' : ''} onClick={() => { setSelected(null); setView('tasks'); }}><span>✓</span>Aufgaben</button>")
app_p.write_text(app)

css += r'''

/* v0.12 Kalender & Terminplanung */
.calendarHeadActions{display:flex;gap:8px;flex-wrap:wrap}.calendarHeadActions .active{border-color:var(--primary);color:var(--primary)}.calendarWeekdays{display:grid;grid-template-columns:repeat(7,1fr);gap:1px;margin-top:18px}.calendarWeekdays b{text-align:center;font-size:11px;color:var(--muted);padding:8px}.calendarGrid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));border:1px solid var(--line);background:var(--line)}.calendarDay{min-height:150px;background:var(--surface);padding:9px;overflow:hidden}.calendarDay.empty{background:var(--surface-2)}.calendarDay.today{box-shadow:inset 0 0 0 2px var(--primary)}.calendarDay>strong{display:block;font-size:12px;margin-bottom:7px}.calendarDay>div{display:flex;flex-direction:column;gap:5px}.calendarEvent{border:0;border-left:3px solid var(--primary);background:var(--primary-soft);text-align:left;padding:6px;border-radius:3px;overflow:hidden;cursor:pointer}.calendarEvent span,.calendarEvent small{display:block;font-size:9px;color:var(--muted)}.calendarEvent b{display:block;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.type-tenant{border-color:var(--accent)!important}.type-inspection{border-color:#7657d6!important}.type-contractor{border-color:var(--success)!important}.calendarAgenda{margin-top:18px}.agendaRow{width:100%;display:grid;grid-template-columns:8px 1fr auto;gap:14px;align-items:center;text-align:left;border:0;border-bottom:1px solid var(--line);background:transparent;padding:14px 0}.agendaMark{width:5px;height:42px;background:var(--primary);border-radius:3px}.agendaRow span{font-size:9px;font-weight:800;color:var(--primary);letter-spacing:.08em}.agendaRow h3{margin:3px 0}.agendaRow p{margin:0;color:var(--muted);font-size:12px}.agendaRow>strong{font-size:12px}.caseCalendar{margin-top:18px}.calendarCreate{border:1px solid var(--line);background:var(--surface-2);padding:16px;margin:14px 0}.caseCalendarList{display:flex;flex-direction:column;gap:8px}.caseCalendarItem{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;border-left:4px solid var(--primary);background:var(--surface-2);padding:12px 14px}.caseCalendarItem>div{display:flex;flex-direction:column;gap:3px}.caseCalendarItem span{font-size:9px;font-weight:800;color:var(--muted);letter-spacing:.08em}.caseCalendarItem small{color:var(--muted)}.caseCalendarItem select{min-width:120px}.caseCalendarItem>strong{font-size:10px;color:var(--success)}@media(max-width:900px){.calendarDay{min-height:110px;padding:5px}.calendarEvent small{display:none}}@media(max-width:680px){.calendarWeekdays,.calendarGrid{grid-template-columns:repeat(7,minmax(44px,1fr));min-width:650px}.calendarPage{overflow-x:auto}.calendarDay{min-height:100px}.agendaRow{grid-template-columns:6px 1fr}.agendaRow>strong{grid-column:2}.caseCalendarItem{grid-template-columns:1fr}}
'''
css_p.write_text(css)
print('v0.12 upgrade prepared')
