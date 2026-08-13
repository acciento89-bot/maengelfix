from pathlib import Path
import json,re
root=Path('.')
schema_p=root/'server/schema.sql'; server_p=root/'server/index.js'; app_p=root/'client/src/App.jsx'; css_p=root/'client/src/maengelfix-pro.css'; pkg_p=root/'server/package.json'
schema=schema_p.read_text(); server=server_p.read_text(); app=app_p.read_text(); css=css_p.read_text(); pkg=json.loads(pkg_p.read_text())

if '-- v0.10: Tarife, Testphase, Limits und Abrechnungsgrundlage' not in schema:
    schema += '''\n\n-- v0.10: Tarife, Testphase, Limits und Abrechnungsgrundlage\nALTER TABLE users ADD COLUMN IF NOT EXISTS plan_code text NOT NULL DEFAULT 'private_free';\nALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status text NOT NULL DEFAULT 'active';\nALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_provider text;\nALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_customer_id text;\nALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_id text;\nALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_current_period_end timestamptz;\n\nALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_status text NOT NULL DEFAULT 'trialing';\nALTER TABLE organizations ADD COLUMN IF NOT EXISTS trial_ends_at timestamptz;\nALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_provider text;\nALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_customer_id text;\nALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_id text;\nALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_current_period_end timestamptz;\nALTER TABLE organizations ADD COLUMN IF NOT EXISTS max_members integer NOT NULL DEFAULT 5;\nALTER TABLE organizations ADD COLUMN IF NOT EXISTS max_properties integer NOT NULL DEFAULT 25;\nALTER TABLE organizations ADD COLUMN IF NOT EXISTS max_units integer NOT NULL DEFAULT 250;\n\nCREATE TABLE IF NOT EXISTS billing_events (\n  id text PRIMARY KEY,\n  provider text NOT NULL,\n  provider_event_id text UNIQUE,\n  organization_id text REFERENCES organizations(id) ON DELETE SET NULL,\n  user_id text REFERENCES users(id) ON DELETE SET NULL,\n  event_type text NOT NULL,\n  payload jsonb NOT NULL DEFAULT '{}'::jsonb,\n  created_at timestamptz NOT NULL DEFAULT now()\n);\nCREATE INDEX IF NOT EXISTS billing_events_org_idx ON billing_events(organization_id,created_at DESC);\n'''
schema_p.write_text(schema)
pkg['version']='0.10.0'; pkg_p.write_text(json.dumps(pkg,ensure_ascii=False,indent=2)+'\n')

# Helpers for subscription state and server-side limits.
helper_anchor='async function scopeForUser(userId) {'
if 'async function billingOrganizationForUser' not in server:
    helpers=r'''async function billingOrganizationForUser(userId) {
  const r=await pool.query(`SELECT o.*,om.role FROM organization_memberships om JOIN organizations o ON o.id=om.organization_id WHERE om.user_id=$1 AND COALESCE(om.active,true)=true LIMIT 1`,[userId]);
  return r.rows[0]||null;
}
function billingState(org){
  if(!org) return {active:false,reason:'none'};
  if(org.subscription_status==='trialing'){
    if(org.trial_ends_at && new Date(org.trial_ends_at)<=new Date()) return {active:false,reason:'trial_expired'};
    return {active:true,reason:'trialing'};
  }
  if(org.subscription_status==='active') return {active:true,reason:'active'};
  return {active:false,reason:org.subscription_status||'inactive'};
}
async function billingUsage(organizationId){
  const r=await pool.query(`SELECT
    (SELECT count(*)::int FROM organization_memberships WHERE organization_id=$1 AND COALESCE(active,true)=true) members,
    (SELECT count(*)::int FROM properties WHERE organization_id=$1) properties,
    (SELECT count(*)::int FROM units u JOIN properties p ON p.id=u.property_id WHERE p.organization_id=$1) units`,[organizationId]);
  return r.rows[0];
}
async function enforceOrganizationLimit(org,kind){
  const state=billingState(org); if(!state.active) return {ok:false,error:'Die Testphase bzw. das Verwaltungs-Abo ist nicht aktiv.'};
  const usage=await billingUsage(org.id); const uk={member:'members',property:'properties',unit:'units'}[kind]; const lk={member:'max_members',property:'max_properties',unit:'max_units'}[kind];
  if(uk && Number(usage[uk])>=Number(org[lk])) return {ok:false,error:`Tariflimit erreicht (${usage[uk]}/${org[lk]}).`};
  return {ok:true,usage};
}

'''
    server=server.replace(helper_anchor,helpers+helper_anchor,1)

# New organizations: 14-day trial and initial B2B limits.
server=server.replace("`INSERT INTO organizations (id, name, plan_code, created_by) VALUES ($1,$2,'business',$3)`", "`INSERT INTO organizations (id,name,plan_code,created_by,subscription_status,trial_ends_at,max_members,max_properties,max_units) VALUES ($1,$2,'business_trial',$3,'trialing',now()+interval '14 days',5,25,250)`")
server=server.replace("{ id: orgId, name, plan_code: 'business', role: 'owner' }", "{ id: orgId, name, plan_code: 'business_trial', role: 'owner', subscription_status: 'trialing' }")

# Enforce member limit before creating a new employee account.
route="app.post('/api/team/members', auth, async (req, res, next) => {"
pos=server.find(route)
if pos!=-1:
    marker="const name = cleanText(req.body.name, 120);"
    m=server.find(marker,pos)
    if m!=-1 and 'enforceOrganizationLimit(organization' not in server[pos:m]:
        server=server[:m]+"const capacity=await enforceOrganizationLimit(organization,'member'); if(!capacity.ok) return res.status(402).json({error:capacity.error});\n    "+server[m:]

# Enforce property and unit limits.
for route,kind in [("app.post('/api/properties', auth",'property'),("app.post('/api/properties/:propertyId/units', auth",'unit')]:
    pos=server.find(route)
    if pos!=-1:
        marker='const organization = await organizationForUser(req.user.id);'
        m=server.find(marker,pos)
        if m!=-1 and m<pos+1600:
            insert=m+len(marker)
            if 'enforceOrganizationLimit' not in server[insert:insert+400]:
                server=server[:insert]+f"\n    if(organization){{const capacity=await enforceOrganizationLimit(await billingOrganizationForUser(req.user.id),'{kind}');if(!capacity.ok)return res.status(402).json({{error:capacity.error}});}}"+server[insert:]

# Billing API: data is real; checkout stays disabled until Stripe keys/product IDs are deliberately configured.
api_anchor="app.get('/api/team', auth, async (req, res, next) => {"
if "app.get('/api/billing/plan'" not in server:
    endpoints=r'''app.get('/api/billing/plan', auth, async (req,res,next)=>{
  try {
    const org=await billingOrganizationForUser(req.user.id);
    if(org){const usage=await billingUsage(org.id);return res.json({scope:'organization',plan:{...org,...billingState(org)},usage,checkoutConfigured:Boolean(process.env.STRIPE_SECRET_KEY&&process.env.STRIPE_PRICE_MANAGEMENT)});}
    const r=await pool.query('SELECT plan_code,subscription_status,subscription_provider,subscription_current_period_end FROM users WHERE id=$1',[req.user.id]);
    res.json({scope:'private',plan:r.rows[0],checkoutConfigured:Boolean(process.env.STRIPE_SECRET_KEY&&process.env.STRIPE_PRICE_PRIVATE)});
  } catch(error){next(error)}
});

app.post('/api/billing/checkout', auth, async (req,res,next)=>{
  try {
    const org=await billingOrganizationForUser(req.user.id);
    if(org&&!['owner','admin'].includes(org.role)) return res.status(403).json({error:'Nur Inhaber und Admins können den Tarif ändern.'});
    const configured=Boolean(process.env.STRIPE_SECRET_KEY && (org?process.env.STRIPE_PRICE_MANAGEMENT:process.env.STRIPE_PRICE_PRIVATE));
    if(!configured) return res.status(503).json({error:'Online-Zahlung ist noch nicht aktiviert. Testphase und Tariflimits funktionieren bereits.'});
    return res.status(501).json({error:'Stripe Checkout wird erst aktiviert, nachdem die endgültigen Preise und Produkt-IDs festgelegt wurden.'});
  } catch(error){next(error)}
});

'''
    server=server.replace(api_anchor,endpoints+api_anchor,1)
server_p.write_text(server)

# Billing UI.
if 'function BillingView()' not in app:
    comp=r'''
function BillingView(){
  const [data,setData]=useState(null);const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  useEffect(()=>{api('/api/billing/plan').then(setData).catch(e=>setError(e.message))},[]);
  async function checkout(){setBusy(true);setError('');try{const r=await api('/api/billing/checkout',{method:'POST'});if(r?.url)window.location.href=r.url}catch(e){setError(e.message)}finally{setBusy(false)}}
  if(!data)return <div className="workspacePage"><div className="emptyCard">Tarif wird geladen…</div></div>;
  const org=data.scope==='organization',p=data.plan,trial=p.subscription_status==='trialing'; const days=p.trial_ends_at?Math.max(0,Math.ceil((new Date(p.trial_ends_at)-new Date())/86400000)):null;
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>TARIF & ABRECHNUNG</span><h1>{org?'MängelFix Verwaltung':'MängelFix Privat'}</h1><p>{org?'Testphase, Tarifstatus und Nutzung deines Verwaltungs-Arbeitsbereichs.':'Tarifstatus deines persönlichen Kontos.'}</p></div></div>{error&&<div className="errorBox">{error}</div>}<section className="workspacePanel billingHero"><div><span>AKTUELLER STATUS</span><h2>{trial?`14-Tage-Testphase · noch ${days} Tag${days===1?'':'e'}`:p.subscription_status==='active'?'Aktiv':'Nicht aktiv'}</h2><p>{org?'Während der Testphase stehen die Verwaltungsfunktionen innerhalb der unten aufgeführten Limits zur Verfügung.':'Dein Privatkonto bleibt unabhängig von Verwaltungs-Arbeitsbereichen.'}</p></div>{org&&<button className="primaryButton" disabled={busy} onClick={checkout}>{busy?'Wird geöffnet…':data.checkoutConfigured?'Verwaltungstarif wählen':'Online-Zahlung noch nicht aktiviert'}</button>}</section>{org&&<div className="billingUsage"><article><span>TEAMMITGLIEDER</span><b>{data.usage.members} / {p.max_members}</b></article><article><span>OBJEKTE</span><b>{data.usage.properties} / {p.max_properties}</b></article><article><span>EINHEITEN</span><b>{data.usage.units} / {p.max_units}</b></article></div>}<section className="workspacePanel billingInfo"><h2>Abrechnung vorbereitet</h2><p>Tarifstatus, Testende, Zahlungsanbieter, Customer-/Subscription-ID und Abrechnungszeitraum sind bereits technisch vorgesehen. Konkrete Europreise und Stripe Checkout werden erst aktiviert, wenn die Preise endgültig festgelegt sind.</p></section></div>;
}

'''
    marker='function AccountSecurityView'
    if marker in app: app=app.replace(marker,comp+marker,1)
    else:
        marker='function TeamView('
        if marker in app: app=app.replace(marker,comp+marker,1)

# Wire content switch, without touching public/root routing.
if "view === 'billing'" not in app:
    app=app.replace("else if (view === 'team') content = <TeamView", "else if (view === 'billing') content = <BillingView />;\n  else if (view === 'team') content = <TeamView",1)
# Add sidebar entry before team if possible.
needle="<button className={view === 'team' ? 'active' : ''}"
if 'Tarif & Abrechnung</button>' not in app and needle in app:
    app=app.replace(needle,"<button className={view === 'billing' ? 'active' : ''} onClick={() => { setSelected(null); setView('billing'); }}><span>€</span>Tarif & Abrechnung</button>"+needle,1)
app_p.write_text(app)

if '/* v0.10 billing */' not in css:
    css += '''\n/* v0.10 billing */\n.billingHero{display:flex;justify-content:space-between;gap:28px;align-items:center}.billingHero>div>span,.billingUsage span{font-size:11px;font-weight:800;letter-spacing:.12em;color:#6f7a86}.billingHero h2{margin:8px 0}.billingUsage{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:18px 0}.billingUsage article{background:#18212b;color:#fff;border-radius:12px;padding:22px}.billingUsage article span{display:block;color:#aeb8c3}.billingUsage article b{display:block;font-size:26px;margin-top:8px}.billingInfo{margin-top:18px}@media(max-width:760px){.billingHero{align-items:stretch;flex-direction:column}.billingUsage{grid-template-columns:1fr}}\n'''
css_p.write_text(css)
print('v0.10 billing foundation prepared')
