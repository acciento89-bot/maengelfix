from pathlib import Path
import json,re
root=Path('.')
schema_path=root/'server/schema.sql'; server_path=root/'server/index.js'; app_path=root/'client/src/App.jsx'; css_path=root/'client/src/maengelfix-pro.css'; pkg_path=root/'server/package.json'
schema=schema_path.read_text(); server=server_path.read_text(); app=app_path.read_text(); css=css_path.read_text(); pkg=json.loads(pkg_path.read_text())

schema_block=r'''

-- v0.10: Tarife, Testphase, Limits & Abrechnungsgrundlage
ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_code text NOT NULL DEFAULT 'private_free';
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status text NOT NULL DEFAULT 'active';
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_provider text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_customer_id text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_id text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_current_period_end timestamptz;

ALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_status text NOT NULL DEFAULT 'trialing';
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS trial_ends_at timestamptz;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_provider text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_customer_id text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_id text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_current_period_end timestamptz;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS max_members integer NOT NULL DEFAULT 5;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS max_properties integer NOT NULL DEFAULT 25;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS max_units integer NOT NULL DEFAULT 250;

CREATE TABLE IF NOT EXISTS billing_events (
 id text PRIMARY KEY,
 provider text NOT NULL,
 provider_event_id text UNIQUE,
 organization_id text REFERENCES organizations(id) ON DELETE SET NULL,
 user_id text REFERENCES users(id) ON DELETE SET NULL,
 event_type text NOT NULL,
 payload jsonb NOT NULL DEFAULT '{}'::jsonb,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS billing_events_org_idx ON billing_events(organization_id,created_at DESC);
'''
if '-- v0.10: Tarife, Testphase, Limits & Abrechnungsgrundlage' not in schema: schema+=schema_block
schema_path.write_text(schema)
pkg['version']='0.10.0'; pkg_path.write_text(json.dumps(pkg,ensure_ascii=False,indent=2)+'\n')
server=re.sub(r"res\.json\(\{ ok: true, service: 'maengelfix', version: '[^']+'[^}]*\}\);","res.json({ ok: true, service: 'maengelfix', version: '0.10.0', mail: smtpConfigured ? 'smtp' : 'manual' });",server,count=1)
server=server.replace("`SELECT o.id, o.name, o.plan_code, om.role\n     FROM organization_memberships", "`SELECT o.id, o.name, o.plan_code, o.subscription_status, o.trial_ends_at, o.subscription_current_period_end, o.max_members, o.max_properties, o.max_units, om.role\n     FROM organization_memberships")

helper_anchor="async function canAccessCase(userId, caseId) {"
if 'function organizationAccessState(' not in server:
 helper=r'''
function organizationAccessState(organization) {
  if (!organization) return {active:false,reason:'none'};
  if (['active','trialing'].includes(organization.subscription_status)) {
    if (organization.subscription_status==='trialing' && organization.trial_ends_at && new Date(organization.trial_ends_at)<=new Date()) return {active:false,reason:'trial_expired'};
    return {active:true,reason:organization.subscription_status};
  }
  return {active:false,reason:organization.subscription_status||'inactive'};
}
async function organizationUsage(organizationId){
 const r=await pool.query(`SELECT
  (SELECT count(*)::int FROM organization_memberships WHERE organization_id=$1) members,
  (SELECT count(*)::int FROM properties WHERE organization_id=$1) properties,
  (SELECT count(*)::int FROM units u JOIN properties p ON p.id=u.property_id WHERE p.organization_id=$1) units`,[organizationId]);
 return r.rows[0];
}
async function requireOrganizationCapacity(organization,kind){
 const state=organizationAccessState(organization); if(!state.active) return {ok:false,error:'Die Testphase bzw. das Verwaltungs-Abo ist nicht aktiv.'};
 const usage=await organizationUsage(organization.id); const limitKey={member:'max_members',property:'max_properties',unit:'max_units'}[kind]; const usageKey={member:'members',property:'properties',unit:'units'}[kind];
 if(limitKey && Number(usage[usageKey])>=Number(organization[limitKey])) return {ok:false,error:`Tariflimit erreicht (${usage[usageKey]}/${organization[limitKey]}).`};
 return {ok:true,usage};
}
'''
 server=server.replace(helper_anchor,helper+helper_anchor)

# New management workspaces start with a 14-day trial and explicit limits.
server=server.replace("`INSERT INTO organizations (id, name, plan_code, created_by) VALUES ($1,$2,'business',$3)`", "`INSERT INTO organizations (id,name,plan_code,created_by,subscription_status,trial_ends_at,max_members,max_properties,max_units) VALUES ($1,$2,'business_trial',$3,'trialing',now()+interval '14 days',5,25,250)`")
server=server.replace("{ id: orgId, name, plan_code: 'business', role: 'owner' }", "{ id: orgId, name, plan_code: 'business_trial', role: 'owner', subscription_status:'trialing' }")
# Enforce team member capacity.
needle="const organization = await organizationForUser(req.user.id);\n    if (!organization || !['owner', 'admin'].includes(organization.role)) {"
pos=server.find("app.post('/api/team/members'")
if pos!=-1:
 end=server.find("const name =",pos); seg=server[pos:end]
 if 'requireOrganizationCapacity' not in seg:
  server=server[:end]+"const capacity=await requireOrganizationCapacity(organization,'member'); if(!capacity.ok) return res.status(402).json({error:capacity.error});\n    "+server[end:]
# Enforce property/unit limits at creation endpoints.
for route,kind in [("app.post('/api/properties'",'property'),("app.post('/api/properties/:propertyId/units'",'unit')]:
 pos=server.find(route)
 if pos!=-1:
  marker="const organization = await organizationForUser(req.user.id);"; m=server.find(marker,pos)
  if m!=-1 and m<server.find("});",pos)+500:
   insert=m+len(marker)
   nearby=server[insert:insert+500]
   if 'requireOrganizationCapacity' not in nearby:
    server=server[:insert]+f"\n    if(organization){{const capacity=await requireOrganizationCapacity(organization,'{kind}');if(!capacity.ok)return res.status(402).json({{error:capacity.error}});}}"+server[insert:]

api_anchor="app.get('/api/notifications', auth, async (req,res,next)=>{"
if "app.get('/api/billing/plan'" not in server:
 endpoints=r'''
app.get('/api/billing/plan',auth,async(req,res,next)=>{try{
 const organization=await organizationForUser(req.user.id);
 if(organization){const usage=await organizationUsage(organization.id);return res.json({scope:'organization',plan:{...organization,...organizationAccessState(organization)},usage,checkoutConfigured:Boolean(process.env.STRIPE_SECRET_KEY)});}
 const u=await pool.query('SELECT plan_code,subscription_status,subscription_provider,subscription_current_period_end FROM users WHERE id=$1',[req.user.id]);
 res.json({scope:'private',plan:u.rows[0],checkoutConfigured:Boolean(process.env.STRIPE_SECRET_KEY)});
}catch(e){next(e)}});

app.post('/api/billing/checkout',auth,async(req,res,next)=>{try{
 const organization=await organizationForUser(req.user.id); const scope=organization?'organization':'private';
 if(organization && !['owner','admin'].includes(organization.role)) return res.status(403).json({error:'Nur Inhaber und Admins können den Tarif ändern.'});
 if(!process.env.STRIPE_SECRET_KEY) return res.status(503).json({error:'Online-Zahlung ist noch nicht aktiviert. Die Tarif- und Limitlogik ist bereits aktiv.'});
 return res.status(501).json({error:'Stripe-Zahlungsstart wird nach Hinterlegung der Stripe-Produkt-IDs aktiviert.',scope});
}catch(e){next(e)}});
'''
 server=server.replace(api_anchor,endpoints+api_anchor)
server_path.write_text(server)

# Client: real prices are intentionally not invented. Show trial and limits, plus billing screen.
app=app.replace("<p>MängelFix bekommt zwei klar getrennte Produktlinien. Die konkreten Preise legen wir vor dem Zahlungsstart fest.</p>","<p>Privat bleibt einfach. Verwaltungen können den vollständigen Team-Arbeitsbereich 14 Tage testen; konkrete Europreise werden erst angezeigt, sobald sie verbindlich festgelegt sind.</p>")
component_anchor="function TeamView() {"
if 'function BillingView()' not in app:
 comp=r'''
function BillingView(){
 const [data,setData]=useState(null);const [error,setError]=useState('');const [busy,setBusy]=useState(false);
 useEffect(()=>{api('/api/billing/plan').then(setData).catch(e=>setError(e.message))},[]);
 async function checkout(){setBusy(true);setError('');try{const x=await api('/api/billing/checkout',{method:'POST'});if(x.url)window.location.href=x.url}catch(e){setError(e.message)}finally{setBusy(false)}}
 if(!data)return <div className="workspacePage"><div className="emptyCard">Tarif wird geladen…</div></div>;
 const org=data.scope==='organization'; const p=data.plan; const trial=p.subscription_status==='trialing'; const trialDays=p.trial_ends_at?Math.max(0,Math.ceil((new Date(p.trial_ends_at)-new Date())/86400000)):null;
 return <div className="workspacePage"><div className="workspaceHeading"><div><span>TARIF & ABRECHNUNG</span><h1>{org?'MängelFix Verwaltung':'MängelFix Privat'}</h1><p>{org?'Tarifstatus, Testphase und Nutzung deines Verwaltungs-Arbeitsbereichs.':'Dein persönlicher MängelFix-Tarif.'}</p></div></div>{error&&<div className="errorBox">{error}</div>}<section className="workspacePanel billingHero"><div><span>AKTUELLER STATUS</span><h2>{trial?`Testphase · noch ${trialDays} Tag${trialDays===1?'':'e'}`:p.subscription_status==='active'?'Aktiv':'Nicht aktiv'}</h2><p>{org?'Die Testphase enthält die Verwaltungsfunktionen innerhalb der unten gezeigten Limits.':'Dein Privatkonto bleibt unabhängig von Hausverwaltungs-Arbeitsbereichen.'}</p></div>{org&&<button className="primaryButton" disabled={busy} onClick={checkout}>{busy?'Wird geöffnet…':data.checkoutConfigured?'Verwaltungstarif wählen':'Zahlung noch nicht aktiviert'}</button>}</section>{org&&<div className="billingUsage"><article><span>MITARBEITER</span><b>{data.usage.members} / {p.max_members}</b></article><article><span>OBJEKTE</span><b>{data.usage.properties} / {p.max_properties}</b></article><article><span>EINHEITEN</span><b>{data.usage.units} / {p.max_units}</b></article></div>}<div className="workspacePanel billingInfo"><h2>Was bereits technisch greift</h2><p>Testphase und Limits werden serverseitig geprüft. Ein UI-Trick kann sie daher nicht umgehen. Die eigentliche Online-Zahlung wird erst freigeschaltet, wenn Stripe-Schlüssel und die endgültigen Produktpreise hinterlegt sind.</p></div></div>;
}

'''
 app=app.replace(component_anchor,comp+component_anchor)
app=app.replace("else if (view === 'audit') content = <AuditView />;", "else if (view === 'audit') content = <AuditView />;\n  else if (view === 'billing') content = <BillingView />;")
old="{management?.organization&&<button className={view === 'audit' ? 'active' : ''} onClick={() => { setSelected(null); setView('audit'); }}><span>A</span>Aktivitätsprotokoll</button>}<button className={view === 'team' ? 'active' : ''}"
new="{management?.organization&&<button className={view === 'audit' ? 'active' : ''} onClick={() => { setSelected(null); setView('audit'); }}><span>A</span>Aktivitätsprotokoll</button>}<button className={view === 'billing' ? 'active' : ''} onClick={() => { setSelected(null); setView('billing'); }}><span>€</span>Tarif & Abrechnung</button><button className={view === 'team' ? 'active' : ''}"
app=app.replace(old,new)
app_path.write_text(app)

css+='''\n/* v0.10 billing */\n.billingHero{display:flex;justify-content:space-between;gap:28px;align-items:center}.billingHero>div>span,.billingUsage span{font-size:11px;font-weight:800;letter-spacing:.12em;color:#6f7a86}.billingHero h2{margin:8px 0}.billingUsage{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:18px 0}.billingUsage article{background:#18212b;color:white;border-radius:12px;padding:22px}.billingUsage article span{display:block;color:#aeb8c3}.billingUsage article b{display:block;font-size:26px;margin-top:8px}.billingInfo{margin-top:18px}@media(max-width:760px){.billingHero{align-items:stretch;flex-direction:column}.billingUsage{grid-template-columns:1fr}}\n'''
css_path.write_text(css)
print('v0.10 upgrade prepared')
