from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / 'server' / 'index.js'
APP = ROOT / 'client' / 'src' / 'App.jsx'
MAIN = ROOT / 'client' / 'src' / 'main.jsx'
CSS = ROOT / 'client' / 'src' / 'v022.css'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        print(f'{label}: already applied')
        return text
    if old not in text:
        raise SystemExit(f'{label}: anchor not found')
    print(f'{label}: applied')
    return text.replace(old, new, 1)


server = SERVER.read_text(encoding='utf-8')
app = APP.read_text(encoding='utf-8')
main = MAIN.read_text(encoding='utf-8')

# 1) Status PATCH: PostgreSQL receives $2 but the SQL did not reference it. Using it
# explicitly prevents the prepared statement from failing with an untyped parameter.
server = replace_once(
    server,
    """       deadline_on=$12, status=$13, purchase_on=$14, purchase_price=$15, warranty_until=$16, desired_resolution=$17, updated_at=now()\n       WHERE id=$1 RETURNING *`,""",
    """       deadline_on=$12, status=$13, purchase_on=$14, purchase_price=$15, warranty_until=$16, desired_resolution=$17, updated_at=now()\n       WHERE id=$1 AND $2::text IS NOT NULL RETURNING *`,""",
    'status patch SQL parameter fix'
)

# Human-readable status labels on the server as well (history + status notification mail).
if '// V022_CASE_STATUS_LABELS' not in server:
    anchor = "const allowedStatuses = new Set(['draft','sent','reply','received','reviewing','commissioned','scheduled','in_progress','resolved']);\n"
    addition = """const allowedStatuses = new Set(['draft','sent','reply','received','reviewing','commissioned','scheduled','in_progress','resolved']);
// V022_CASE_STATUS_LABELS
const serverCaseStatusLabels = {draft:'Entwurf',sent:'Versendet',reply:'Rückmeldung',received:'Eingegangen',reviewing:'In Prüfung',commissioned:'Auftrag erstellt',scheduled:'Termin geplant',in_progress:'In Bearbeitung',resolved:'Erledigt'};
function serverCaseStatusLabel(status){return serverCaseStatusLabels[status] || status;}
"""
    server = replace_once(server, anchor, addition, 'server status labels')

server = replace_once(
    server,
    "[id(), req.params.caseId, req.user.id, 'status', `Status geändert: ${nextStatus}`]",
    "[id(), req.params.caseId, req.user.id, 'status', `Status geändert: ${serverCaseStatusLabel(nextStatus)}`]",
    'status history label'
)
server = replace_once(
    server,
    "text:`Der Status von „${old.title}“ wurde geändert. Neuer Status: ${nextStatus}.`",
    "text:`Der Status von „${old.title}“ wurde geändert. Neuer Status: ${serverCaseStatusLabel(nextStatus)}.`",
    'status mail label'
)

# 2) Branded, Gmail-friendly app mail template.
mail_pattern = re.compile(
    r"async function sendAppMail\(\{ to, subject, heading, text, buttonLabel, buttonUrl \}\) \{.*?\n\}\n\nasync function issueVerification",
    re.S,
)
if '// V022_BRANDED_APP_MAIL' not in server:
    match = mail_pattern.search(server)
    if not match:
        raise SystemExit('sendAppMail: function anchor not found')
    mail_function = r'''async function sendAppMail({ to, subject, heading, text, buttonLabel, buttonUrl }) {
  // V022_BRANDED_APP_MAIL
  if (!mailer || !to) return false;
  const safeHeading = escapeHtml(heading || subject);
  const plainText = String(text || '');
  const safeText = escapeHtml(plainText).replace(/\r?\n/g,'<br>');
  const safeButtonUrl = buttonUrl ? escapeHtml(buttonUrl) : '';
  const safeButtonLabel = escapeHtml(buttonLabel || 'MängelFix öffnen');
  const preview = escapeHtml(`${heading || subject} – ${plainText.replace(/\s+/g,' ').trim().slice(0,120)}`);
  const button = buttonUrl ? `<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:26px 0 4px"><tr><td bgcolor="#2457D6" style="border-radius:8px"><a href="${safeButtonUrl}" style="display:inline-block;padding:13px 20px;font-family:Arial,sans-serif;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px">${safeButtonLabel}</a></td></tr></table>` : '';
  const html = `<!doctype html><html><body style="margin:0;padding:0;background:#F3F6FA"><div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">${preview}</div><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;background:#F3F6FA"><tr><td align="center" style="padding:30px 14px"><table role="presentation" width="620" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:620px;background:#ffffff;border:1px solid #E3E8EF;border-radius:14px;overflow:hidden"><tr><td style="background:#2457D6;padding:22px 28px"><table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr><td style="width:42px;height:42px;background:#ffffff;border-radius:10px;text-align:center;font-family:Arial,sans-serif;font-size:24px;font-weight:800;color:#2457D6">✓</td><td style="padding-left:13px;font-family:Arial,sans-serif;color:#ffffff"><div style="font-size:20px;font-weight:800;line-height:1.1">MängelFix</div><div style="font-size:12px;opacity:.86;margin-top:3px">Kamilunavo</div></td></tr></table></td></tr><tr><td style="padding:34px 32px 30px;font-family:Arial,sans-serif;color:#18212B"><div style="font-size:12px;font-weight:700;letter-spacing:.08em;color:#2457D6;text-transform:uppercase;margin-bottom:10px">MängelFix Benachrichtigung</div><h1 style="margin:0 0 18px;font-size:25px;line-height:1.25;color:#18212B">${safeHeading}</h1><div style="font-size:15px;line-height:1.7;color:#3D4856">${safeText}</div>${button}</td></tr><tr><td style="border-top:1px solid #E8EDF2;padding:20px 32px 24px;font-family:Arial,sans-serif;color:#768292;font-size:12px;line-height:1.55"><b style="color:#4A5563">Kamilunavo · MängelFix</b><br>Diese Nachricht wurde automatisch von MängelFix gesendet. Antworten auf diese E-Mail werden nicht automatisch einem Vorgang zugeordnet.</td></tr></table></td></tr></table></body></html>`;
  await mailer.sendMail({
    from: process.env.SMTP_FROM || 'MängelFix <noreply@kamilunavo.com>',
    to,
    subject,
    text: `${heading || subject}\n\n${plainText}${buttonUrl ? `\n\n${buttonLabel || 'MängelFix öffnen'}: ${buttonUrl}` : ''}\n\nKamilunavo · MängelFix`,
    html
  });
  return true;
}

async function issueVerification'''
    server = server[:match.start()] + mail_function + server[match.end():]
    print('branded app mail: applied')
else:
    print('branded app mail: already applied')

# 3) Deadline worker: claim a reminder stage atomically before sending it. This prevents
# duplicate messages even if more than one web container runs the worker.
deadline_pattern = re.compile(
    r"async function processCaseDeadlineEscalations\(\)\{.*?setInterval\(processCaseDeadlineEscalations,60\*60\*1000\);",
    re.S,
)
if '// V022_DEADLINE_ATOMIC_CLAIM' not in server:
    match = deadline_pattern.search(server)
    if not match:
        raise SystemExit('deadline worker: anchor not found')
    deadline_worker = r'''async function processCaseDeadlineEscalations(){
 // V022_DEADLINE_ATOMIC_CLAIM
 try {
  const due=await pool.query(`
    SELECT c.*,u.email,u.name,
      CASE WHEN c.deadline_on<current_date THEN 3 WHEN c.deadline_on=current_date THEN 2 ELSE 1 END AS due_stage
    FROM defect_cases c
    JOIN users u ON u.id=c.user_id
    WHERE c.archived_at IS NULL
      AND c.status<>'resolved'
      AND c.deadline_on IS NOT NULL
      AND ((c.deadline_on=current_date+3 AND c.deadline_reminder_stage<1)
        OR (c.deadline_on=current_date AND c.deadline_reminder_stage<2)
        OR (c.deadline_on<current_date AND c.deadline_reminder_stage<3))
    ORDER BY c.deadline_on,c.created_at
    LIMIT 200`);
  for(const c of due.rows){
   const stage=Number(c.due_stage||0);
   if(!stage)continue;
   const claimed=await pool.query(`UPDATE defect_cases SET deadline_reminder_stage=$2,last_deadline_notification_at=now() WHERE id=$1 AND deadline_reminder_stage<$2 RETURNING id`,[c.id,stage]);
   if(!claimed.rowCount)continue;
   const title=stage===3?'Frist überfällig':stage===2?'Frist heute fällig':'Frist in 3 Tagen';
   const deadlineIso=c.deadline_on instanceof Date?c.deadline_on.toISOString().slice(0,10):String(c.deadline_on).slice(0,10);
   const [year,month,day]=deadlineIso.split('-');
   const deadlineLabel=year&&month&&day?`${day}.${month}.${year}`:deadlineIso;
   try{await createNotification({userId:c.user_id,organizationId:c.organization_id,caseId:c.id,type:'deadline',title,body:c.title,link:`/app?case=${c.id}`})}catch(e){console.error('Deadline in-app notification failed',e)}
   if(mailer&&c.email){try{await sendAppMail({to:c.email,subject:`MängelFix · ${title}`,heading:title,text:`${c.title}\nFrist: ${deadlineLabel}`,buttonLabel:'Vorgang öffnen',buttonUrl:`${appOrigin}/app?case=${c.id}`})}catch(e){console.error('Deadline mail failed',e)}}
  }
 } catch(e){console.error('Deadline escalation failed',e)}
}
setTimeout(processCaseDeadlineEscalations,25000);setInterval(processCaseDeadlineEscalations,60*60*1000);'''
    server = server[:match.start()] + deadline_worker + server[match.end():]
    print('deadline worker atomic claim: applied')
else:
    print('deadline worker atomic claim: already applied')

# 4) Hard-delete endpoint. Database cascades clean case-owned rows; files are removed
# from /data/uploads after a successful commit.
if '// V022_CASE_DELETE_ENDPOINT' not in server:
    insert_anchor = "\napp.post('/api/cases/:caseId/events', auth, async (req, res, next) => {"
    if insert_anchor not in server:
        raise SystemExit('case delete endpoint: insertion anchor not found')
    delete_endpoint = r'''

// V022_CASE_DELETE_ENDPOINT
app.delete('/api/cases/:caseId', auth, async (req,res,next)=>{
  const client=await pool.connect();
  let transactionOpen=false;
  try{
    const accessible=await canAccessCase(req.user.id,req.params.caseId);
    if(!accessible)return res.status(404).json({error:'Mangel nicht gefunden.'});
    const viewerOrganization=await organizationForUser(req.user.id);
    const organizationCase=Boolean(accessible.organization_id);
    const isManagement=Boolean(viewerOrganization&&viewerOrganization.id===accessible.organization_id);
    if(organizationCase&&!isManagement)return res.status(403).json({error:'Ein an eine Hausverwaltung übermittelter Vorgang kann vom Mieter nicht dauerhaft gelöscht werden.'});
    if(organizationCase&&!['owner','admin'].includes(viewerOrganization?.role))return res.status(403).json({error:'Nur Inhaber und Admins können Verwaltungsvorgänge dauerhaft löschen.'});
    if(!organizationCase&&accessible.user_id!==req.user.id)return res.status(403).json({error:'Keine Berechtigung zum Löschen dieses Vorgangs.'});

    const [caseFiles,orderFiles]=await Promise.all([
      client.query('SELECT stored_name FROM attachments WHERE case_id=$1',[accessible.id]),
      client.query(`SELECT woa.stored_name FROM work_order_attachments woa JOIN work_orders wo ON wo.id=woa.work_order_id WHERE wo.case_id=$1`,[accessible.id])
    ]);
    const storedNames=[...caseFiles.rows,...orderFiles.rows].map(x=>x.stored_name).filter(Boolean);

    await client.query('BEGIN');transactionOpen=true;
    if(organizationCase)await writeAudit({organizationId:accessible.organization_id,userId:req.user.id,caseId:accessible.id,action:'case_deleted',entityType:'case',entityId:accessible.id,summary:`Vorgang „${accessible.title}“ dauerhaft gelöscht.`});
    await client.query('DELETE FROM defect_cases WHERE id=$1',[accessible.id]);
    await client.query('COMMIT');transactionOpen=false;

    for(const storedName of storedNames){
      try{fs.unlinkSync(path.join(uploadDir,path.basename(storedName)))}catch(error){if(error?.code!=='ENOENT')console.error('Case file cleanup failed',storedName,error)}
    }
    res.status(204).end();
  }catch(error){
    if(transactionOpen){try{await client.query('ROLLBACK')}catch{}}
    next(error);
  }finally{client.release()}
});
'''
    server = server.replace(insert_anchor, delete_endpoint + insert_anchor, 1)
    print('case delete endpoint: applied')
else:
    print('case delete endpoint: already applied')

# 5) Web UI delete action on the case detail page.
if '// V022_CASE_DELETE_ACTION' not in app:
    change_status_anchor = """  async function changeStatus(status) {
    setBusy(true); setError('');
    try { await api(`/api/cases/${caseId}`, { method: 'PATCH', body: JSON.stringify({ status }) }); await load(); onUpdated(); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
"""
    if change_status_anchor not in app:
        raise SystemExit('client delete action: changeStatus anchor not found')
    delete_action = change_status_anchor + r'''

  // V022_CASE_DELETE_ACTION
  async function deleteCase() {
    const title=data?.case?.title||'diesen Vorgang';
    if(!window.confirm(`Vorgang „${title}“ wirklich dauerhaft löschen?\n\nFotos, Dokumente, Verlauf und zugehörige Inhalte werden ebenfalls gelöscht. Dieser Schritt kann nicht rückgängig gemacht werden.`))return;
    setBusy(true);setError('');
    try{await api(`/api/cases/${caseId}`,{method:'DELETE'});await onUpdated?.();onBack();}
    catch(err){setError(err.message)}
    finally{setBusy(false)}
  }
'''
    app = app.replace(change_status_anchor, delete_action, 1)
    print('client delete action: applied')
else:
    print('client delete action: already applied')

old_actions = """        <div className=\"detailActions\">{!profileComplete && <button className=\"profileWarning\" onClick={onProfile}>Absender ergänzen</button>}<a className=\"primaryButton linkButton\" href={`/api/cases/${item.id}/pdf`} target=\"_blank\" rel=\"noreferrer\">PDF öffnen</a><a className=\"secondaryButton linkButton\" href={`/api/cases/${item.id}/pdf?download=1`}>PDF herunterladen</a></div>"""
new_actions = """        <div className=\"detailActions\">{!profileComplete && <button className=\"profileWarning\" onClick={onProfile}>Absender ergänzen</button>}<a className=\"primaryButton linkButton\" href={`/api/cases/${item.id}/pdf`} target=\"_blank\" rel=\"noreferrer\">PDF öffnen</a><a className=\"secondaryButton linkButton\" href={`/api/cases/${item.id}/pdf?download=1`}>PDF herunterladen</a>{!(item.submitted_by_tenant && data.viewerRole!=='management')&&<button type=\"button\" className=\"caseDeleteButton\" disabled={busy} onClick={deleteCase}>Vorgang löschen</button>}</div>"""
app = replace_once(app, old_actions, new_actions, 'client delete button')

# 6) Load the small v0.22 stylesheet.
if "import './v022.css';" not in main:
    main = replace_once(main, "import './v019-landing.css';\n", "import './v019-landing.css';\nimport './v022.css';\n", 'v022 stylesheet import')

SERVER.write_text(server, encoding='utf-8')
APP.write_text(app, encoding='utf-8')
MAIN.write_text(main, encoding='utf-8')
CSS.write_text('''/* MängelFix v0.22 – website case reliability */
.detailActions{flex-wrap:wrap;justify-content:flex-end}
.caseDeleteButton{appearance:none;border:1px solid #efb4b4;background:#fff7f7;color:#b42318;border-radius:8px;padding:12px 16px;font:inherit;font-weight:750;cursor:pointer;transition:background .15s ease,border-color .15s ease,transform .15s ease}
.caseDeleteButton:hover{background:#fff0f0;border-color:#e58b8b;transform:translateY(-1px)}
.caseDeleteButton:disabled{opacity:.55;cursor:not-allowed;transform:none}
@media (max-width:760px){.detailActions{width:100%;justify-content:flex-start}.detailActions>a,.detailActions>button{flex:1 1 auto;text-align:center}.caseDeleteButton{width:100%}}
''', encoding='utf-8')
print('MängelFix v0.22 website reliability patch completed.')
