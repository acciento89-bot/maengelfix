from pathlib import Path
import json,re
root=Path('.')
schema_p=root/'server/schema.sql'; server_p=root/'server/index.js'; app_p=root/'client/src/App.jsx'; css_p=root/'client/src/maengelfix-pro.css'; pkg_p=root/'server/package.json'; index_p=root/'client/index.html'
schema=schema_p.read_text(); server=server_p.read_text(); app=app_p.read_text(); css=css_p.read_text(); pkg=json.loads(pkg_p.read_text()); index=index_p.read_text()

# -------------------- Schema --------------------
if '-- v0.15: Produktionsvorbereitung ohne Serverzugriff' not in schema:
    schema += r'''

-- v0.15: Produktionsvorbereitung ohne Serverzugriff
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin boolean NOT NULL DEFAULT false;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS archived_at timestamptz;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS purchase_on date;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS purchase_price numeric(12,2);
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS desired_resolution text;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS warranty_until date;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS deadline_reminder_stage integer NOT NULL DEFAULT 0;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS last_deadline_notification_at timestamptz;
ALTER TABLE attachments ADD COLUMN IF NOT EXISTS evidence_type text NOT NULL DEFAULT 'photo';
ALTER TABLE attachments ADD COLUMN IF NOT EXISTS note text;
ALTER TABLE attachments ADD COLUMN IF NOT EXISTS captured_at timestamptz;
ALTER TABLE attachments ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'user';
CREATE INDEX IF NOT EXISTS defect_cases_archive_idx ON defect_cases(user_id,archived_at,updated_at DESC);
CREATE INDEX IF NOT EXISTS defect_cases_org_archive_idx ON defect_cases(organization_id,archived_at,updated_at DESC);

CREATE TABLE IF NOT EXISTS work_order_attachments (
  id text PRIMARY KEY,
  work_order_id text NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
  uploaded_by_user_id text REFERENCES users(id) ON DELETE SET NULL,
  uploaded_by_type text NOT NULL DEFAULT 'contractor',
  original_name text NOT NULL,
  stored_name text NOT NULL,
  mime_type text NOT NULL,
  size_bytes integer NOT NULL,
  note text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS work_order_attachments_order_idx ON work_order_attachments(work_order_id,created_at);
'''
schema_p.write_text(schema)
pkg['version']='0.15.0'; pkg_p.write_text(json.dumps(pkg,ensure_ascii=False,indent=2)+'\n')
server=re.sub(r"res\.json\(\{ ok: true, service: 'maengelfix', version: '[^']+'[^}]*\}\);","res.json({ ok: true, service: 'maengelfix', version: '0.15.0', mail: smtpConfigured ? 'smtp' : 'manual', stripe: Boolean(process.env.STRIPE_SECRET_KEY) });",server,count=1)

# -------------------- Fix upload declaration order --------------------
# v0.13 introduced routes that use `upload` before its declaration. Move the upload setup before route registration.
upload_match=re.search(r"\nconst storage = multer\.diskStorage\(\{.*?\n\}\);\n\nconst upload = multer\(\{.*?\n\}\);\n",server,re.S)
if upload_match:
    upload_block=upload_match.group(0)
    server=server[:upload_match.start()]+"\n"+server[upload_match.end():]
    insert_anchor="app.use(cookieParser());"
    server=server.replace(insert_anchor,insert_anchor+upload_block,1)

# Dedicated evidence upload accepts images and PDFs.
if 'const evidenceUpload = multer(' not in server:
    ev=r'''
const evidenceUpload = multer({
  storage,
  limits: { fileSize: 15 * 1024 * 1024, files: 10 },
  fileFilter: (_req,file,cb) => cb(null,/^image\/(jpeg|png|webp|heic|heif)$/.test(file.mimetype) || file.mimetype==='application/pdf')
});
'''
    server=server.replace("const upload = multer({", "const upload = multer({",1)
    m=re.search(r"const upload = multer\(\{.*?\n\}\);",server,re.S)
    if m: server=server[:m.end()]+"\n"+ev+server[m.end():]

# -------------------- Stripe webhook before JSON parser --------------------
if "'/api/billing/stripe/webhook'" not in server:
    server=server.replace("app.use(express.json({ limit: '1mb' }));","app.post('/api/billing/stripe/webhook', express.raw({type:'application/json'}), handleStripeWebhook);\napp.use(express.json({ limit: '1mb' }));",1)

# -------------------- Helpers --------------------
helper_anchor="function escapeHtml(value) {"
if 'async function isPlatformAdmin(' not in server:
    helpers=r'''
function configuredAdminEmails(){return String(process.env.ADMIN_EMAILS||'').split(',').map(x=>x.trim().toLowerCase()).filter(Boolean)}
async function isPlatformAdmin(user){
  if(!user)return false;
  if(configuredAdminEmails().includes(String(user.email||'').toLowerCase()))return true;
  const r=await pool.query('SELECT is_admin FROM users WHERE id=$1',[user.id]);return Boolean(r.rows[0]?.is_admin);
}
async function requirePlatformAdmin(req,res){if(!(await isPlatformAdmin(req.user))){res.status(403).json({error:'Adminzugriff erforderlich.'});return false}return true}

async function stripeRequest(pathname,params){
  if(!process.env.STRIPE_SECRET_KEY)throw new Error('Stripe ist nicht konfiguriert.');
  const body=new URLSearchParams();for(const [k,v] of Object.entries(params||{})){if(v!==undefined&&v!==null)body.append(k,String(v))}
  const response=await fetch(`https://api.stripe.com/v1/${pathname}`,{method:'POST',headers:{Authorization:`Bearer ${process.env.STRIPE_SECRET_KEY}`,'Content-Type':'application/x-www-form-urlencoded'},body});
  const data=await response.json();if(!response.ok)throw new Error(data?.error?.message||'Stripe-Anfrage fehlgeschlagen.');return data;
}
function stripePriceFor(scope,cycle){
 const annual=cycle==='yearly';
 return scope==='organization'?(annual?process.env.STRIPE_PRICE_MANAGEMENT_YEARLY:process.env.STRIPE_PRICE_MANAGEMENT_MONTHLY):(annual?process.env.STRIPE_PRICE_PRIVATE_YEARLY:process.env.STRIPE_PRICE_PRIVATE_MONTHLY);
}
function parseStripeSignature(header){const out={};for(const part of String(header||'').split(',')){const [k,v]=part.split('=');if(k&&v)(out[k]||(out[k]=[])).push(v)}return out}
function verifyStripeWebhook(raw,header){
 const secret=process.env.STRIPE_WEBHOOK_SECRET;if(!secret)return false;const sig=parseStripeSignature(header);const t=Number(sig.t?.[0]);if(!t||Math.abs(Date.now()/1000-t)>300)return false;const expected=crypto.createHmac('sha256',secret).update(`${t}.${raw.toString('utf8')}`).digest('hex');return (sig.v1||[]).some(v=>{try{const a=Buffer.from(v,'hex'),b=Buffer.from(expected,'hex');return a.length===b.length&&crypto.timingSafeEqual(a,b)}catch{return false}})
}
async function applyStripeSubscription(sub,eventId,eventType,payload){
 const customer=String(sub.customer||'');const subscriptionId=String(sub.id||'');const status=String(sub.status||'');const end=sub.current_period_end?new Date(sub.current_period_end*1000):null;
 const org=await pool.query('SELECT id FROM organizations WHERE subscription_customer_id=$1 OR subscription_id=$2 LIMIT 1',[customer,subscriptionId]);
 const user=org.rowCount?null:await pool.query('SELECT id FROM users WHERE subscription_customer_id=$1 OR subscription_id=$2 LIMIT 1',[customer,subscriptionId]);
 if(org.rowCount)await pool.query(`UPDATE organizations SET subscription_provider='stripe',subscription_customer_id=$2,subscription_id=$3,subscription_status=$4,subscription_current_period_end=$5,updated_at=now() WHERE id=$1`,[org.rows[0].id,customer,subscriptionId,status==='active'||status==='trialing'?'active':status,end]);
 if(user?.rowCount)await pool.query(`UPDATE users SET subscription_provider='stripe',subscription_customer_id=$2,subscription_id=$3,subscription_status=$4,subscription_current_period_end=$5 WHERE id=$1`,[user.rows[0].id,customer,subscriptionId,status==='active'||status==='trialing'?'active':status,end]);
 await pool.query(`INSERT INTO billing_events (id,provider,provider_event_id,organization_id,user_id,event_type,payload) VALUES ($1,'stripe',$2,$3,$4,$5,$6) ON CONFLICT (provider_event_id) DO NOTHING`,[id(),eventId,org.rows[0]?.id||null,user?.rows[0]?.id||null,eventType,payload]);
}
async function handleStripeWebhook(req,res){
 try{if(!verifyStripeWebhook(req.body,req.headers['stripe-signature']))return res.status(400).send('invalid signature');const event=JSON.parse(req.body.toString('utf8'));if(event.type.startsWith('customer.subscription.'))await applyStripeSubscription(event.data.object,event.id,event.type,event);if(event.type==='checkout.session.completed'){const s=event.data.object;const orgId=s.metadata?.organization_id||null,userId=s.metadata?.user_id||null;if(orgId)await pool.query(`UPDATE organizations SET subscription_provider='stripe',subscription_customer_id=$2,subscription_id=$3 WHERE id=$1`,[orgId,String(s.customer||''),String(s.subscription||'')]);if(userId)await pool.query(`UPDATE users SET subscription_provider='stripe',subscription_customer_id=$2,subscription_id=$3 WHERE id=$1`,[userId,String(s.customer||''),String(s.subscription||'')]);await pool.query(`INSERT INTO billing_events (id,provider,provider_event_id,organization_id,user_id,event_type,payload) VALUES ($1,'stripe',$2,$3,$4,$5,$6) ON CONFLICT (provider_event_id) DO NOTHING`,[id(),event.id,orgId,userId,event.type,event]);}res.json({received:true})}catch(e){console.error('Stripe webhook failed',e);res.status(500).send('webhook error')}
}
'''
    server=server.replace(helper_anchor,helpers+helper_anchor,1)

# -------------------- Billing routes --------------------
old_checkout=re.search(r"app\.post\('/api/billing/checkout'.*?\n\}\);",server,re.S)
if old_checkout:
    new_checkout=r'''app.post('/api/billing/checkout', auth, async (req,res,next)=>{
  try{
    const org=await billingOrganizationForUser(req.user.id);if(org&&!['owner','admin'].includes(org.role))return res.status(403).json({error:'Nur Inhaber und Admins können den Tarif ändern.'});
    const scope=org?'organization':'private';const cycle=req.body.cycle==='yearly'?'yearly':'monthly';const price=stripePriceFor(scope,cycle);if(!process.env.STRIPE_SECRET_KEY||!price)return res.status(503).json({error:'Online-Zahlung ist noch nicht vollständig konfiguriert.'});
    const params={'mode':'subscription','line_items[0][price]':price,'line_items[0][quantity]':'1','success_url':`${appOrigin}/app?view=billing&checkout=success`,'cancel_url':`${appOrigin}/app?view=billing&checkout=cancel`,'allow_promotion_codes':'true','metadata[scope]':scope};
    if(org)params['metadata[organization_id]']=org.id;else params['metadata[user_id]']=req.user.id;
    const existing=org?.subscription_customer_id||req.user.subscription_customer_id;if(existing)params.customer=existing;else params.customer_email=req.user.email;
    const session=await stripeRequest('checkout/sessions',params);res.json({url:session.url});
  }catch(e){next(e)}
});
app.post('/api/billing/portal',auth,async(req,res,next)=>{try{const org=await billingOrganizationForUser(req.user.id);if(org&&!['owner','admin'].includes(org.role))return res.status(403).json({error:'Nur Inhaber und Admins können die Abrechnung verwalten.'});const customer=org?.subscription_customer_id||req.user.subscription_customer_id;if(!process.env.STRIPE_SECRET_KEY||!customer)return res.status(503).json({error:'Noch kein Stripe-Kundenkonto vorhanden.'});const portal=await stripeRequest('billing_portal/sessions',{customer,return_url:`${appOrigin}/app?view=billing`});res.json({url:portal.url})}catch(e){next(e)}});'''
    server=server[:old_checkout.start()]+new_checkout+server[old_checkout.end():]
# billing plan config matrix
server=server.replace("checkoutConfigured:Boolean(process.env.STRIPE_SECRET_KEY&&process.env.STRIPE_PRICE_MANAGEMENT)","checkoutConfigured:Boolean(process.env.STRIPE_SECRET_KEY&&(process.env.STRIPE_PRICE_MANAGEMENT_MONTHLY||process.env.STRIPE_PRICE_MANAGEMENT_YEARLY)),cycles:{monthly:Boolean(process.env.STRIPE_PRICE_MANAGEMENT_MONTHLY),yearly:Boolean(process.env.STRIPE_PRICE_MANAGEMENT_YEARLY)}")
server=server.replace("checkoutConfigured:Boolean(process.env.STRIPE_SECRET_KEY&&process.env.STRIPE_PRICE_PRIVATE)","checkoutConfigured:Boolean(process.env.STRIPE_SECRET_KEY&&(process.env.STRIPE_PRICE_PRIVATE_MONTHLY||process.env.STRIPE_PRICE_PRIVATE_YEARLY)),cycles:{monthly:Boolean(process.env.STRIPE_PRICE_PRIVATE_MONTHLY),yearly:Boolean(process.env.STRIPE_PRICE_PRIVATE_YEARLY)}")

# -------------------- Search, archive, deadlines, evidence --------------------
case_anchor="app.get('/api/cases', auth, async (req, res, next) => {"
if "app.get('/api/search/cases'" not in server:
    endpoints=r'''
app.get('/api/search/cases',auth,async(req,res,next)=>{try{
 const org=await organizationForUser(req.user.id);const q=cleanText(req.query.q,180)||'';const status=cleanText(req.query.status,40)||'';const category=cleanText(req.query.category,80)||'';const context=cleanText(req.query.context,40)||'';const archived=String(req.query.archived||'')==='1';const params=[req.user.id,org?.id||null,`%${q}%`,status,category,context,archived];
 const r=await pool.query(`SELECT c.*,p.name property_name,u.label unit_name,au.name assigned_user_name,(SELECT count(*)::int FROM attachments a WHERE a.case_id=c.id) attachment_count FROM defect_cases c LEFT JOIN properties p ON p.id=c.property_id LEFT JOIN units u ON u.id=c.unit_id LEFT JOIN users au ON au.id=c.assigned_user_id WHERE ((c.organization_id IS NULL AND c.user_id=$1) OR ($2::text IS NOT NULL AND c.organization_id=$2)) AND (($7=true AND c.archived_at IS NOT NULL) OR ($7=false AND c.archived_at IS NULL)) AND ($3='%%' OR c.title ILIKE $3 OR c.description ILIKE $3 OR c.reference_label ILIKE $3 OR c.subject_label ILIKE $3 OR c.recipient_name ILIKE $3 OR c.property_label ILIKE $3) AND ($4='' OR c.status=$4) AND ($5='' OR c.category=$5) AND ($6='' OR c.case_context=$6) ORDER BY c.updated_at DESC LIMIT 300`,params);res.json({cases:r.rows})
}catch(e){next(e)}});
app.post('/api/cases/:caseId/archive',auth,async(req,res,next)=>{try{const c=await canAccessCase(req.user.id,req.params.caseId);if(!c)return res.status(404).json({error:'Mangel nicht gefunden.'});const archive=req.body.archived!==false;const r=await pool.query('UPDATE defect_cases SET archived_at=$2,updated_at=now() WHERE id=$1 RETURNING *',[c.id,archive?new Date():null]);if(c.organization_id)await writeAudit({organizationId:c.organization_id,userId:req.user.id,caseId:c.id,action:archive?'case_archived':'case_restored',entityType:'case',entityId:c.id,summary:archive?'Vorgang archiviert.':'Vorgang wiederhergestellt.'});res.json({case:r.rows[0]})}catch(e){next(e)}});
app.get('/api/deadlines/overview',auth,async(req,res,next)=>{try{const org=await organizationForUser(req.user.id);const r=await pool.query(`SELECT c.id,c.title,c.deadline_on,c.status,c.property_label,c.case_context,CASE WHEN c.deadline_on<current_date THEN 'overdue' WHEN c.deadline_on=current_date THEN 'today' WHEN c.deadline_on<=current_date+3 THEN 'soon' ELSE 'later' END urgency FROM defect_cases c WHERE c.archived_at IS NULL AND c.status<>'resolved' AND c.deadline_on IS NOT NULL AND ((c.organization_id IS NULL AND c.user_id=$1) OR ($2::text IS NOT NULL AND c.organization_id=$2)) ORDER BY c.deadline_on`,[req.user.id,org?.id||null]);res.json({deadlines:r.rows})}catch(e){next(e)}});
app.post('/api/cases/:caseId/evidence',auth,evidenceUpload.array('files',10),async(req,res,next)=>{try{const c=await canAccessCase(req.user.id,req.params.caseId);if(!c)return res.status(404).json({error:'Mangel nicht gefunden.'});const type=['photo','document','before','after','invoice','delivery_note','other'].includes(req.body.evidenceType)?req.body.evidenceType:'photo';const out=[];for(const file of req.files||[]){const a=await pool.query(`INSERT INTO attachments (id,case_id,user_id,original_name,stored_name,mime_type,size_bytes,evidence_type,note,captured_at,source) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'user') RETURNING id,original_name,mime_type,size_bytes,evidence_type,note,captured_at,created_at`,[id(),c.id,req.user.id,cleanText(file.originalname,250),file.filename,file.mimetype,file.size,type,cleanText(req.body.note,800),req.body.capturedAt||null]);out.push(a.rows[0])}await pool.query('UPDATE defect_cases SET updated_at=now() WHERE id=$1',[c.id]);res.status(201).json({attachments:out})}catch(e){next(e)}});
'''
    server=server.replace(case_anchor,endpoints+case_anchor,1)
# enrich case attachment selects
server=server.replace("SELECT id, original_name, mime_type, size_bytes, created_at FROM attachments","SELECT id, original_name, mime_type, size_bytes, evidence_type, note, captured_at, source, created_at FROM attachments")

# -------------------- Contractor photo proof --------------------
contractor_anchor="app.get('/api/contractor/work-orders/:token', async (req,res,next)=>{"
if "contractor/work-orders/:token/attachments" not in server:
    ctr=r'''
app.post('/api/contractor/work-orders/:token/attachments',upload.array('images',5),async(req,res,next)=>{try{const o=await pool.query('SELECT id,token_expires_at FROM work_orders WHERE token_hash=$1',[tokenHash(req.params.token)]);if(!o.rowCount)return res.status(404).json({error:'Arbeitsauftrag nicht gefunden.'});if(new Date(o.rows[0].token_expires_at)<=new Date())return res.status(410).json({error:'Auftragslink ist abgelaufen.'});const out=[];for(const file of req.files||[]){const r=await pool.query(`INSERT INTO work_order_attachments (id,work_order_id,uploaded_by_type,original_name,stored_name,mime_type,size_bytes,note) VALUES ($1,$2,'contractor',$3,$4,$5,$6,$7) RETURNING id,original_name,mime_type,size_bytes,note,created_at`,[id(),o.rows[0].id,cleanText(file.originalname,250),file.filename,file.mimetype,file.size,cleanText(req.body.note,800)]);out.push(r.rows[0])}res.status(201).json({attachments:out})}catch(e){next(e)}});
app.get('/api/contractor/work-orders/:token/attachments/:attachmentId',async(req,res,next)=>{try{const r=await pool.query(`SELECT a.*,wo.token_expires_at FROM work_order_attachments a JOIN work_orders wo ON wo.id=a.work_order_id WHERE a.id=$1 AND wo.token_hash=$2`,[req.params.attachmentId,tokenHash(req.params.token)]);if(!r.rowCount)return res.status(404).end();if(new Date(r.rows[0].token_expires_at)<=new Date())return res.status(410).end();res.type(r.rows[0].mime_type).sendFile(path.join(uploadDir,r.rows[0].stored_name))}catch(e){next(e)}});
'''
    server=server.replace(contractor_anchor,ctr+contractor_anchor,1)
# append attachments to contractor payload query by separate lookup easiest
server=server.replace("res.json({order});","const photos=await pool.query('SELECT id,original_name,mime_type,size_bytes,note,created_at FROM work_order_attachments WHERE work_order_id=$1 ORDER BY created_at',[order.id]);res.json({order,attachments:photos.rows});",1)

# -------------------- Admin APIs --------------------
notif_anchor="app.get('/api/notifications', auth, async (req,res,next)=>{"
if "app.get('/api/admin/me'" not in server:
    admin=r'''
app.get('/api/admin/me',auth,async(req,res,next)=>{try{res.json({admin:await isPlatformAdmin(req.user)})}catch(e){next(e)}});
app.get('/api/admin/overview',auth,async(req,res,next)=>{try{if(!(await requirePlatformAdmin(req,res)))return;const [u,o,c,subs,mails]=await Promise.all([pool.query('SELECT count(*)::int n FROM users'),pool.query('SELECT count(*)::int n FROM organizations'),pool.query(`SELECT count(*)::int total,count(*) FILTER(WHERE status<>'resolved')::int open FROM defect_cases`),pool.query(`SELECT count(*) FILTER(WHERE subscription_status='active')::int active,count(*) FILTER(WHERE subscription_status='trialing')::int trialing FROM organizations`),pool.query(`SELECT count(*)::int events FROM billing_events`)]);res.json({users:u.rows[0].n,organizations:o.rows[0].n,cases:c.rows[0],subscriptions:subs.rows[0],billingEvents:mails.rows[0].events,mailConfigured:Boolean(mailer),stripeConfigured:Boolean(process.env.STRIPE_SECRET_KEY),webhookConfigured:Boolean(process.env.STRIPE_WEBHOOK_SECRET)})}catch(e){next(e)}});
app.get('/api/admin/users',auth,async(req,res,next)=>{try{if(!(await requirePlatformAdmin(req,res)))return;const r=await pool.query(`SELECT u.id,u.name,u.email,u.created_at,u.plan_code,u.subscription_status,u.is_admin,(SELECT count(*)::int FROM defect_cases c WHERE c.user_id=u.id) case_count FROM users u ORDER BY u.created_at DESC LIMIT 500`);res.json({users:r.rows})}catch(e){next(e)}});
app.get('/api/admin/organizations',auth,async(req,res,next)=>{try{if(!(await requirePlatformAdmin(req,res)))return;const r=await pool.query(`SELECT o.id,o.name,o.plan_code,o.subscription_status,o.trial_ends_at,o.created_at,(SELECT count(*)::int FROM organization_memberships om WHERE om.organization_id=o.id AND COALESCE(om.active,true)) members,(SELECT count(*)::int FROM defect_cases c WHERE c.organization_id=o.id) cases FROM organizations o ORDER BY o.created_at DESC LIMIT 500`);res.json({organizations:r.rows})}catch(e){next(e)}});
'''
    server=server.replace(notif_anchor,admin+notif_anchor,1)

# -------------------- Deadline worker --------------------
listen_anchor="app.listen(port, '0.0.0.0', () => {"
if 'async function processCaseDeadlineEscalations()' not in server:
    worker=r'''
async function processCaseDeadlineEscalations(){
 try{const due=await pool.query(`SELECT c.*,u.email,u.name FROM defect_cases c JOIN users u ON u.id=c.user_id WHERE c.archived_at IS NULL AND c.status<>'resolved' AND c.deadline_on IS NOT NULL AND ((c.deadline_on=current_date+3 AND c.deadline_reminder_stage<1) OR (c.deadline_on=current_date AND c.deadline_reminder_stage<2) OR (c.deadline_on<current_date AND c.deadline_reminder_stage<3)) LIMIT 200`);for(const c of due.rows){const stage=new Date(c.deadline_on)<new Date(new Date().toISOString().slice(0,10))?3:(String(c.deadline_on).slice(0,10)===new Date().toISOString().slice(0,10)?2:1);const title=stage===3?'Frist überfällig':stage===2?'Frist heute fällig':'Frist in 3 Tagen';await createNotification({userId:c.user_id,organizationId:c.organization_id,caseId:c.id,type:'deadline',title,body:c.title,link:`/app?case=${c.id}`});if(mailer&&c.email)try{await sendAppMail({to:c.email,subject:`MängelFix: ${title}`,heading:title,text:`${c.title}\nFrist: ${new Date(c.deadline_on).toLocaleDateString('de-DE')}`,buttonLabel:'Vorgang öffnen',buttonUrl:`${appOrigin}/app?case=${c.id}`})}catch(e){console.error('Deadline mail failed',e)}await pool.query('UPDATE defect_cases SET deadline_reminder_stage=$2,last_deadline_notification_at=now() WHERE id=$1',[c.id,stage]);}}catch(e){console.error('Deadline escalation failed',e)}}
setTimeout(processCaseDeadlineEscalations,25000);setInterval(processCaseDeadlineEscalations,60*60*1000);

'''
    server=server.replace(listen_anchor,worker+listen_anchor,1)
server_p.write_text(server)

# -------------------- Client --------------------
# Extend general private form.
app=app.replace("counterpartyType:'',discoveredOn:today", "counterpartyType:'',purchaseOn:'',purchasePrice:'',warrantyUntil:'',desiredResolution:'',discoveredOn:today")
# insert private detail fields after generic date grid marker
marker="<label>Rückmeldung / Frist bis<input type=\"date\" value={form.deadlineOn} onChange={e => field('deadlineOn', e.target.value)} /></label></div>"
if marker in app and 'Gewünschte Lösung' not in app:
    extra="<label>Rückmeldung / Frist bis<input type=\"date\" value={form.deadlineOn} onChange={e => field('deadlineOn', e.target.value)} /></label></div>{form.caseContext!=='housing'&&<div className=\"privateExtraFields\"><div className=\"formGrid two\"><label>Kauf- / Leistungsdatum<input type=\"date\" value={form.purchaseOn} onChange={e=>field('purchaseOn',e.target.value)}/></label><label>Kaufpreis / Auftragswert (€)<input type=\"number\" step=\"0.01\" min=\"0\" value={form.purchasePrice} onChange={e=>field('purchasePrice',e.target.value)}/></label><label>Garantie / Zusage bis<input type=\"date\" value={form.warrantyUntil} onChange={e=>field('warrantyUntil',e.target.value)}/></label><label>Gewünschte Lösung<select value={form.desiredResolution} onChange={e=>field('desiredResolution',e.target.value)}><option value=\"\">Noch offen</option><option value=\"repair\">Reparatur / Nachbesserung</option><option value=\"replacement\">Ersatz</option><option value=\"refund\">Rückerstattung</option><option value=\"price_reduction\">Preisminderung</option><option value=\"other\">Andere Lösung</option></select></label></div></div>}"
    app=app.replace(marker,extra,1)

# Add server create fields using follow-up patch endpoint instead of modifying huge insert: update immediately after creation response row.
# Client will patch after creation automatically via existing endpoint if extra fields are supported; add server patch fields below separately.
# Extend PATCH SQL with new fields.
old="deadline_on=$12, status=$13, updated_at=now()"
new="deadline_on=$12, status=$13, purchase_on=$14, purchase_price=$15, warranty_until=$16, desired_resolution=$17, updated_at=now()"
if old in server:
    server=server.replace(old,new,1)
# Adjust patch params if pattern exists.
needle="nextStatus\n      ]"
if needle in server:
    server=server.replace(needle,"nextStatus,\n        req.body.purchaseOn ?? old.purchase_on,\n        req.body.purchasePrice===''?null:(req.body.purchasePrice ?? old.purchase_price),\n        req.body.warrantyUntil ?? old.warranty_until,\n        cleanText(req.body.desiredResolution ?? old.desired_resolution,80)\n      ]",1)
# save updated server again after patch
server_p.write_text(server)

# New components before BillingView.
component_anchor="function BillingView(){"
if 'function SearchArchiveView(' not in app:
    components=r'''
function SearchArchiveView({onSelect}){
 const [form,setForm]=useState({q:'',status:'',category:'',context:'',archived:false});const [rows,setRows]=useState([]);const [error,setError]=useState('');async function load(next=form){const p=new URLSearchParams();if(next.q)p.set('q',next.q);if(next.status)p.set('status',next.status);if(next.category)p.set('category',next.category);if(next.context)p.set('context',next.context);if(next.archived)p.set('archived','1');try{setRows((await api(`/api/search/cases?${p}`)).cases)}catch(e){setError(e.message)}}useEffect(()=>{load()},[]);function change(k,v){const n={...form,[k]:v};setForm(n);load(n)}async function archive(x,archived){try{await api(`/api/cases/${x.id}/archive`,{method:'POST',body:JSON.stringify({archived})});await load()}catch(e){setError(e.message)}}return <div className="workspacePage"><div className="workspaceHeading"><div><span>SUCHE & ARCHIV</span><h1>Vorgänge wiederfinden</h1><p>Suche über Titel, Beschreibung, Referenz, Empfänger und Objekt.</p></div></div>{error&&<div className="errorBox">{error}</div>}<div className="searchFilters"><input placeholder="Suchen…" value={form.q} onChange={e=>change('q',e.target.value)}/><select value={form.status} onChange={e=>change('status',e.target.value)}><option value="">Alle Status</option>{Object.entries(statusLabels).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select><select value={form.category} onChange={e=>change('category',e.target.value)}><option value="">Alle Kategorien</option>{categories.map(c=><option key={c}>{c}</option>)}</select><select value={form.context} onChange={e=>change('context',e.target.value)}><option value="">Alle Bereiche</option>{Object.entries(caseContexts).map(([k,v])=><option key={k} value={k}>{v.label}</option>)}</select><label><input type="checkbox" checked={form.archived} onChange={e=>change('archived',e.target.checked)}/> Archiv anzeigen</label></div><div className="searchResults">{rows.map(x=><article key={x.id}><button onClick={()=>onSelect(x.id)}><span>{caseContexts[x.case_context]?.label||x.category}</span><h3>{x.title}</h3><p>{[x.subject_label||x.property_label,x.reference_label,x.recipient_name].filter(Boolean).join(' · ')}</p></button><div><span className={`status status-${x.status}`}>{statusLabels[x.status]}</span><button className="secondaryButton" onClick={()=>archive(x,!form.archived)}>{form.archived?'Wiederherstellen':'Archivieren'}</button></div></article>)}</div></div>;
}
function DeadlineCenterView({onSelect}){const [rows,setRows]=useState([]);const [error,setError]=useState('');useEffect(()=>{api('/api/deadlines/overview').then(x=>setRows(x.deadlines)).catch(e=>setError(e.message))},[]);return <div className="workspacePage"><div className="workspaceHeading"><div><span>FRISTEN & ESKALATIONEN</span><h1>Was als Nächstes fällig wird</h1><p>Automatische Hinweise werden drei Tage vorher, am Fälligkeitstag und bei Überfälligkeit erzeugt.</p></div></div>{error&&<div className="errorBox">{error}</div>}<div className="deadlineCenter">{rows.map(x=><button key={x.id} className={`deadlineCenterRow ${x.urgency}`} onClick={()=>onSelect(x.id)}><div><span>{x.urgency==='overdue'?'ÜBERFÄLLIG':x.urgency==='today'?'HEUTE':x.urgency==='soon'?'BALD':'GEPLANT'}</span><h3>{x.title}</h3><p>{x.property_label||caseContexts[x.case_context]?.label}</p></div><b>{fmtDate(x.deadline_on)}</b></button>)}</div></div>}
function AdminView(){const [data,setData]=useState(null),[users,setUsers]=useState([]),[orgs,setOrgs]=useState([]),[error,setError]=useState('');useEffect(()=>{Promise.all([api('/api/admin/overview'),api('/api/admin/users'),api('/api/admin/organizations')]).then(([a,u,o])=>{setData(a);setUsers(u.users);setOrgs(o.organizations)}).catch(e=>setError(e.message))},[]);if(!data)return <div className="workspacePage"><div className="emptyCard">{error||'Adminbereich wird geladen…'}</div></div>;return <div className="workspacePage adminPage"><div className="workspaceHeading"><div><span>KAMILUNAVO ADMIN</span><h1>MängelFix Betrieb</h1><p>Nutzer, Verwaltungen und technische Integrationen auf einen Blick.</p></div></div><div className="analyticsMetrics"><article><span>NUTZER</span><b>{data.users}</b></article><article><span>VERWALTUNGEN</span><b>{data.organizations}</b></article><article><span>VORGÄNGE</span><b>{data.cases.total}</b></article><article><span>AKTIVE ABOS</span><b>{data.subscriptions.active}</b></article></div><section className="workspacePanel adminHealth"><h2>Integrationen</h2><div><span>SMTP <b>{data.mailConfigured?'bereit':'nicht konfiguriert'}</b></span><span>Stripe <b>{data.stripeConfigured?'bereit':'nicht konfiguriert'}</b></span><span>Webhook <b>{data.webhookConfigured?'bereit':'nicht konfiguriert'}</b></span></div></section><div className="adminColumns"><section className="workspacePanel"><h2>Neueste Nutzer</h2>{users.slice(0,20).map(u=><div className="adminRow" key={u.id}><span><b>{u.name}</b><small>{u.email}</small></span><strong>{u.case_count} Fälle</strong></div>)}</section><section className="workspacePanel"><h2>Verwaltungen</h2>{orgs.slice(0,20).map(o=><div className="adminRow" key={o.id}><span><b>{o.name}</b><small>{o.subscription_status}</small></span><strong>{o.cases} Fälle · {o.members} Nutzer</strong></div>)}</section></div></div>}
'''
    app=app.replace(component_anchor,components+component_anchor,1)

# Billing UI: monthly/yearly + portal.
app=app.replace("async function checkout(){setBusy(true);setError('');try{const r=await api('/api/billing/checkout',{method:'POST'});if(r?.url)window.location.href=r.url}catch(e){setError(e.message)}finally{setBusy(false)}}","async function checkout(cycle){setBusy(true);setError('');try{const r=await api('/api/billing/checkout',{method:'POST',body:JSON.stringify({cycle})});if(r?.url)window.location.href=r.url}catch(e){setError(e.message)}finally{setBusy(false)}} async function portal(){setBusy(true);setError('');try{const r=await api('/api/billing/portal',{method:'POST'});if(r?.url)window.location.href=r.url}catch(e){setError(e.message)}finally{setBusy(false)}}")
app=app.replace("{org&&<button className=\"primaryButton\" disabled={busy} onClick={checkout}>{busy?'Wird geöffnet…':data.checkoutConfigured?'Verwaltungstarif wählen':'Online-Zahlung noch nicht aktiviert'}</button>}","<div className=\"billingActions\">{data.checkoutConfigured&&data.cycles?.monthly&&<button className=\"primaryButton\" disabled={busy} onClick={()=>checkout('monthly')}>Monatlich wählen</button>}{data.checkoutConfigured&&data.cycles?.yearly&&<button className=\"primaryButton\" disabled={busy} onClick={()=>checkout('yearly')}>Jährlich wählen</button>}{!data.checkoutConfigured&&<button className=\"primaryButton\" disabled>Online-Zahlung noch nicht aktiviert</button>}{p.subscription_customer_id&&<button className=\"secondaryButton\" disabled={busy} onClick={portal}>Abo verwalten</button>}</div>")

# Case evidence panel, replacing simple upload affordance while keeping gallery.
old_ev='<section className="contentCard"><div className="sectionTitle"><div><div className="cardKicker">BEWEISSICHERUNG</div><h3>Fotos & Belege</h3><p className="muted">Bis zu 5 Bilder pro Upload, jeweils maximal 10 MB.</p></div><label className="secondaryButton uploadButton">Bilder hinzufügen<input type="file" accept="image/*" multiple onChange={uploadImages} /></label></div>'
if old_ev in app:
    new_ev='<section className="contentCard"><div className="sectionTitle"><div><div className="cardKicker">BEWEISSICHERUNG</div><h3>Fotos, Dokumente & Belege</h3><p className="muted">Vorher/Nachher-Fotos, Rechnungen, Lieferscheine oder PDF-Dokumente direkt am Vorgang.</p></div><label className="secondaryButton uploadButton">Belege hinzufügen<input type="file" accept="image/*,application/pdf" multiple onChange={async e=>{const fd=new FormData();[...e.target.files].forEach(f=>fd.append(\'files\',f));try{await api(`/api/cases/${caseId}/evidence`,{method:\'POST\',body:fd});await load();onUpdated()}catch(err){setError(err.message)}e.target.value=\'\'}} /></label></div>'
    app=app.replace(old_ev,new_ev,1)
# gallery support PDFs
app=app.replace("<img src={`/api/attachments/${file.id}`} alt={file.original_name} /><span>{file.original_name}</span>","{file.mime_type==='application/pdf'?<div className=\"pdfEvidence\">PDF</div>:<img src={`/api/attachments/${file.id}`} alt={file.original_name} />}<span>{file.original_name}{file.evidence_type&&file.evidence_type!=='photo'?` · ${file.evidence_type}`:''}</span>")

# Contractor portal upload.
portal_marker="{data.order.contractor_note&&<div className=\"lastContractorNote\"><b>Letzte Rückmeldung</b><p>{data.order.contractor_note}</p></div>}"
if portal_marker in app and 'Arbeitsfotos' not in app:
    add=portal_marker+"<div className=\"contractorEvidence\"><h3>Arbeitsfotos</h3><label className=\"secondaryButton uploadButton\">Fotos hochladen<input type=\"file\" accept=\"image/*\" multiple onChange={async e=>{const fd=new FormData();[...e.target.files].forEach(f=>fd.append('images',f));try{await api(`/api/contractor/work-orders/${token}/attachments`,{method:'POST',body:fd});await load()}catch(x){setError(x.message)}e.target.value=''}}/></label><div className=\"contractorPhotoGrid\">{(data.attachments||[]).map(a=><a key={a.id} target=\"_blank\" rel=\"noreferrer\" href={`/api/contractor/work-orders/${token}/attachments/${a.id}`}><img src={`/api/contractor/work-orders/${token}/attachments/${a.id}`} alt={a.original_name}/></a>)}</div></div>"
    app=app.replace(portal_marker,add,1)

# Routes in workspace.
app=app.replace("else if (view === 'deadlines') content = <DeadlinesView cases={cases} onSelect={setSelected} />;","else if (view === 'deadlines') content = <DeadlineCenterView onSelect={setSelected} />;\n  else if (view === 'search') content = <SearchArchiveView onSelect={setSelected} />;")
app=app.replace("else if (view === 'billing') content = <BillingView />;","else if (view === 'billing') content = <BillingView />;\n  else if (view === 'admin') content = <AdminView />;")
# Admin discovery.
app=app.replace("const [unreadNotifications,setUnreadNotifications]=useState(0);","const [unreadNotifications,setUnreadNotifications]=useState(0);const [isAdmin,setIsAdmin]=useState(false);")
app=app.replace("api('/api/management/overview').then(setManagement).catch(()=>setManagement({organization:null}));","api('/api/management/overview').then(setManagement).catch(()=>setManagement({organization:null})); api('/api/admin/me').then(x=>setIsAdmin(Boolean(x.admin))).catch(()=>setIsAdmin(false));")
# Sidebar insert search after cases and admin before bottom.
case_btn="<button className={view === 'cases' || selected ? 'active' : ''} onClick={() => { setSelected(null); setView('cases'); }}><span>M</span>Mängel <b>{cases.filter(x => x.status !== 'resolved').length}</b></button>"
if case_btn in app and "setView('search')" not in app:
    app=app.replace(case_btn,case_btn+"<button className={view === 'search' ? 'active' : ''} onClick={() => { setSelected(null); setView('search'); }}><span>S</span>Suche & Archiv</button>",1)
team_btn="<button className={view === 'team' ? 'active' : ''} onClick={() => { setSelected(null); setView('team'); }}><span>T</span>{management?.organization ? 'Team' : 'Verwaltung'}</button>"
if team_btn in app and 'Kamilunavo Admin' not in app:
    app=app.replace(team_btn,team_btn+"{isAdmin&&<button className={view === 'admin' ? 'active' : ''} onClick={() => { setSelected(null); setView('admin'); }}><span>K</span>Kamilunavo Admin</button>}",1)
app_p.write_text(app)

# PWA manifest + service worker registration without caching HTML navigations.
if 'rel="manifest"' not in index:
    index=index.replace('<link rel="icon" type="image/svg+xml" href="/maengelfix-mark.svg" />','<link rel="icon" type="image/svg+xml" href="/maengelfix-mark.svg" />\n    <link rel="manifest" href="/manifest.webmanifest" />\n    <meta name="apple-mobile-web-app-capable" content="yes" />\n    <meta name="apple-mobile-web-app-status-bar-style" content="default" />\n    <meta name="apple-mobile-web-app-title" content="MängelFix" />')
    index=index.replace('</body>',"    <script>if('serviceWorker' in navigator){window.addEventListener('load',()=>navigator.serviceWorker.register('/sw.js').catch(()=>{}))}</script>\n  </body>")
index_p.write_text(index)

css += r'''
/* v0.15 Produktionsvorbereitung */
.searchFilters{display:grid;grid-template-columns:2fr repeat(3,1fr) auto;gap:10px;margin:18px 0}.searchFilters input,.searchFilters select{border:1px solid #d8dfe3;border-radius:9px;padding:11px;background:#fff}.searchFilters label{display:flex;gap:7px;align-items:center;font-size:12px;font-weight:700}.searchResults{display:grid;gap:9px}.searchResults article{display:flex;justify-content:space-between;gap:15px;background:#fff;border:1px solid #dfe5e8;border-radius:11px;padding:15px}.searchResults article>button{flex:1;text-align:left;background:transparent;border:0}.searchResults h3{margin:3px 0}.searchResults p{margin:0;color:#68747d}.searchResults article>div{display:flex;align-items:center;gap:8px}.deadlineCenter{display:grid;gap:9px}.deadlineCenterRow{display:flex;justify-content:space-between;text-align:left;border:1px solid #dfe4e7;background:#fff;border-left:5px solid #73808a;border-radius:10px;padding:15px}.deadlineCenterRow.soon{border-left-color:#d98b22}.deadlineCenterRow.today,.deadlineCenterRow.overdue{border-left-color:#b42318}.deadlineCenterRow span{font-size:10px;font-weight:800;letter-spacing:.08em}.deadlineCenterRow h3{margin:4px 0}.deadlineCenterRow p{margin:0;color:#68747d}.pdfEvidence{height:135px;display:grid;place-items:center;background:#eef1f3;font-size:30px;font-weight:900;color:#b42318}.contractorEvidence{margin-top:22px;border-top:1px solid #e0e5e8;padding-top:16px}.contractorPhotoGrid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}.contractorPhotoGrid img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:8px}.adminHealth>div{display:flex;gap:10px;flex-wrap:wrap}.adminHealth span{background:#eef1f3;padding:10px 13px;border-radius:8px}.adminColumns{display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-top:15px}.adminRow{display:flex;justify-content:space-between;gap:14px;border-bottom:1px solid #e4e8ea;padding:10px 0}.adminRow span small{display:block;color:#78828b}.billingActions{display:flex;gap:8px;flex-wrap:wrap}.privateExtraFields{background:#f5f7f8;border-radius:10px;padding:14px;margin-top:-2px}@media(max-width:900px){.searchFilters{grid-template-columns:1fr 1fr}.adminColumns{grid-template-columns:1fr}}@media(max-width:620px){.searchFilters{grid-template-columns:1fr}.searchResults article{flex-direction:column}.searchResults article>div{justify-content:space-between}.deadlineCenterRow{flex-direction:column;gap:8px}}
'''
css_p.write_text(css)
print('v0.15 product completion prepared')
