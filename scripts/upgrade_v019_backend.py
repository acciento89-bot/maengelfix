from pathlib import Path
import json,re
r=Path('.')
sp=r/'server/index.js'; scp=r/'server/schema.sql'; pp=r/'server/package.json'
s=sp.read_text(); sc=scp.read_text(); pkg=json.loads(pp.read_text())
pkg['version']='0.19.0'; pp.write_text(json.dumps(pkg,ensure_ascii=False,indent=2)+'\n')
s=re.sub(r"version: '[^']+'","version: '0.19.0'",s,count=1)
if '-- v0.19 onboarding and private entitlements' not in sc:
 sc+="\n-- v0.19 onboarding and private entitlements\nALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed_at timestamptz;\nALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_use_case text;\n"
scp.write_text(sc)

s=re.sub(r"function publicUser\(row\) \{.*?\n\}",'''function publicUser(row) {\n  return {\n    id: row.id, name: row.name, email: row.email,\n    street: row.street || '', postalCode: row.postal_code || '', city: row.city || '', country: row.country || 'Deutschland', phone: row.phone || '',\n    emailVerified: Boolean(row.email_verified_at), planCode: row.plan_code || 'private_free', subscriptionStatus: row.subscription_status || 'active',\n    subscriptionCurrentPeriodEnd: row.subscription_current_period_end || null, onboardingCompleted: Boolean(row.onboarding_completed_at), onboardingUseCase: row.onboarding_use_case || null\n  };\n}''',s,count=1,flags=re.S)
s=s.replace("u.phone, u.email_verified_at\n       FROM sessions","u.phone, u.email_verified_at, u.plan_code, u.subscription_status, u.subscription_current_period_end, u.onboarding_completed_at, u.onboarding_use_case\n       FROM sessions")
s=s.replace("phone, email_verified_at\n       FROM users WHERE email","phone, email_verified_at, plan_code, subscription_status, subscription_current_period_end, onboarding_completed_at, onboarding_use_case\n       FROM users WHERE email")
s=s.replace("RETURNING id, name, email, street, postal_code, city, country, phone, email_verified_at`,","RETURNING id, name, email, street, postal_code, city, country, phone, email_verified_at, plan_code, subscription_status, subscription_current_period_end, onboarding_completed_at, onboarding_use_case`,")

anchor="function setSessionCookie(res, token) {"
if 'function hasPrivatePro(user)' not in s:
 h='''function hasPrivatePro(user){return user?.plan_code==='private_pro'&&['active','trialing'].includes(String(user?.subscription_status||''))}\nasync function privateEntitlements(userId,user){\n const org=await billingOrganizationForUser(userId);\n if(org){const st=billingState(org);return {scope:'organization',pro:Boolean(st.active),planCode:org.plan_code,status:org.subscription_status,trialEndsAt:org.trial_ends_at||null,usage:await billingUsage(org.id),limits:{members:org.max_members,properties:org.max_properties,units:org.max_units},features:{advancedEvidence:true,deadlines:true,tasks:true,calendar:true,analytics:true,archive:true,inspections:true}}}\n const q=(await pool.query(`SELECT count(*) FILTER(WHERE status<>'resolved' AND archived_at IS NULL)::int active_cases FROM defect_cases WHERE user_id=$1`,[userId])).rows[0];const pro=hasPrivatePro(user);\n return {scope:'private',pro,planCode:user?.plan_code||'private_free',status:user?.subscription_status||'active',usage:{activeCases:q.active_cases||0},limits:{maxActiveCases:pro?null:5,maxPhotosPerCase:pro?null:3},features:{advancedEvidence:pro,deadlines:pro,tasks:pro,calendar:pro,analytics:pro,archive:pro,inspections:pro}}\n}\nasync function privateProFeature(req,res,next){try{const org=await billingOrganizationForUser(req.user.id);if(org){if(billingState(org).active)return next();return res.status(402).json({error:'Die Testphase bzw. das Verwaltungs-Abo ist nicht aktiv.',code:'PLAN_INACTIVE'})}if(hasPrivatePro(req.user))return next();res.status(402).json({error:'Diese Funktion gehört zu MängelFix Privat Pro.',code:'PRO_REQUIRED'})}catch(e){next(e)}}\n\n'''
 s=s.replace(anchor,h+anchor,1)
s=s.replace("WHERE om.user_id = $1\n     ORDER BY om.created_at","WHERE om.user_id = $1 AND COALESCE(om.active,true)=true\n     ORDER BY om.created_at")

me="app.get('/api/me', auth, (req, res) => res.json({ user: publicUser(req.user) }));"
if "app.get('/api/entitlements'" not in s:
 s=s.replace(me,me+'''\n\napp.get('/api/entitlements',auth,async(req,res,next)=>{try{res.json(await privateEntitlements(req.user.id,req.user))}catch(e){next(e)}});\napp.patch('/api/onboarding',auth,async(req,res,next)=>{try{const useCase=['private','management'].includes(req.body.useCase)?req.body.useCase:'private';const q=await pool.query(`UPDATE users SET onboarding_use_case=$2,onboarding_completed_at=now() WHERE id=$1 RETURNING id,name,email,street,postal_code,city,country,phone,email_verified_at,plan_code,subscription_status,subscription_current_period_end,onboarding_completed_at,onboarding_use_case`,[req.user.id,useCase]);res.json({user:publicUser(q.rows[0])})}catch(e){next(e)}});''')

if 'function billingCatalog(scope)' not in s:
 s=s.replace("function publicPricingCatalog(){return Object.values(pricingCatalog)}","function publicPricingCatalog(){return Object.values(pricingCatalog)}\nfunction billingCatalog(scope){return publicPricingCatalog().filter(p=>p.scope===scope).map(p=>({...p,checkout:{monthly:Boolean(stripePriceForPlan(p.code,'monthly')),yearly:Boolean(stripePriceForPlan(p.code,'yearly'))}}))}")
s=s.replace("catalog:publicPricingCatalog().filter(p=>p.scope==='organization')","catalog:billingCatalog('organization')").replace("catalog:publicPricingCatalog().filter(p=>p.scope==='private')","catalog:billingCatalog('private')")

def gate(method,path):
 global s
 pat=rf"app\.{method}\('{re.escape(path)}',\s*auth,\s*(?!privateProFeature)"
 s=re.sub(pat,lambda m:m.group(0)+'privateProFeature, ',s,count=1)
for m,p in [('get','/api/analytics'),('get','/api/search/cases'),('post','/api/cases/:caseId/archive'),('get','/api/deadlines/overview'),('post','/api/cases/:caseId/evidence'),('get','/api/tasks'),('get','/api/cases/:caseId/tasks'),('post','/api/cases/:caseId/tasks'),('patch','/api/tasks/:taskId'),('get','/api/calendar'),('post','/api/cases/:caseId/calendar'),('patch','/api/calendar/:eventId'),('delete','/api/calendar/:eventId'),('get','/api/inspections'),('post','/api/inspections'),('get','/api/inspections/:protocolId'),('post','/api/inspections/:protocolId/rooms'),('patch','/api/inspection-rooms/:roomId'),('post','/api/inspections/:protocolId/findings'),('post','/api/inspection-findings/:findingId/attachments'),('get','/api/inspection-attachments/:attachmentId'),('post','/api/inspection-findings/:findingId/create-case'),('post','/api/inspections/:protocolId/complete'),('get','/api/inspections/:protocolId/pdf')]:gate(m,p)

ca="    const ownOrganization = await organizationForUser(req.user.id);\n    let destination = null;"
if 'FREE_ACTIVE_CASE_LIMIT_V019' not in s:
 repl="""    const ownOrganization = await organizationForUser(req.user.id);\n    // FREE_ACTIVE_CASE_LIMIT_V019\n    if(!ownOrganization&&!hasPrivatePro(req.user)){const n=(await client.query(`SELECT count(*)::int n FROM defect_cases WHERE user_id=$1 AND status<>'resolved' AND archived_at IS NULL`,[req.user.id])).rows[0].n;if(n>=5){await client.query('ROLLBACK');return res.status(402).json({error:'Privat Free erlaubt bis zu 5 aktive Vorgänge. Erledige einen Vorgang oder wechsle zu Privat Pro.',code:'PRO_REQUIRED'})}if(req.body.deadlineOn){await client.query('ROLLBACK');return res.status(402).json({error:'Fristen und automatische Erinnerungen gehören zu Privat Pro.',code:'PRO_REQUIRED'})}}\n    let destination = null;"""
 if ca not in s: raise SystemExit('case create anchor missing')
 s=s.replace(ca,repl,1)
pa="    const old = current.rows[0];\n    const nextStatus = status || old.status;"
if 'FREE_DEADLINE_PATCH_V019' not in s:
 s=s.replace(pa,"    const old = current.rows[0];\n    // FREE_DEADLINE_PATCH_V019\n    if(req.body.deadlineOn&&!(await organizationForUser(req.user.id))&&!hasPrivatePro(req.user))return res.status(402).json({error:'Fristen und automatische Erinnerungen gehören zu Privat Pro.',code:'PRO_REQUIRED'});\n    const nextStatus = status || old.status;",1)
photo="    if (!accessible) return res.status(404).json({ error: 'Mangel nicht gefunden.' });\n    const created = [];"
if 'FREE_PHOTO_LIMIT_V019' not in s:
 s=s.replace(photo,"    if (!accessible) return res.status(404).json({ error: 'Mangel nicht gefunden.' });\n    // FREE_PHOTO_LIMIT_V019\n    const photoOrg=await organizationForUser(req.user.id);if(!photoOrg&&!hasPrivatePro(req.user)){const n=(await pool.query('SELECT count(*)::int n FROM attachments WHERE case_id=$1',[req.params.caseId])).rows[0].n;if(n+(req.files||[]).length>3){for(const f of req.files||[]){try{fs.unlinkSync(f.path)}catch{}}return res.status(402).json({error:'Privat Free erlaubt bis zu 3 Fotos pro Vorgang. Für weitere Fotos und Dokumente benötigst du Privat Pro.',code:'PRO_REQUIRED'})}}\n    const created = [];",1)

# no internal management task leak to tenant
needle="    const accessible=await canAccessCase(req.user.id,req.params.caseId); if(!accessible) return res.status(404).json({error:'Vorgang nicht gefunden.'});\n    const result=await pool.query(`SELECT t.*,u.name AS assigned_name FROM case_tasks"
if 'TASK_TENANT_PRIVACY_V019' not in s and needle in s:
 s=s.replace(needle,"    const accessible=await canAccessCase(req.user.id,req.params.caseId); if(!accessible) return res.status(404).json({error:'Vorgang nicht gefunden.'});\n    // TASK_TENANT_PRIVACY_V019\n    if(accessible.organization_id){const vo=await organizationForUser(req.user.id);if(!vo||vo.id!==accessible.organization_id)return res.json({tasks:[],members:[],organizationId:null})}\n    const result=await pool.query(`SELECT t.*,u.name AS assigned_name FROM case_tasks",1)
sp.write_text(s)
print('v0.19 backend prepared')
