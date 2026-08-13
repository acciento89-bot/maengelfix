from pathlib import Path
import json,re
root=Path('.')
app_p=root/'client/src/App.jsx'; server_p=root/'server/index.js'; schema_p=root/'server/schema.sql'; pkg_p=root/'server/package.json'; css_p=root/'client/src/maengelfix-pro.css'
app=app_p.read_text(); server=server_p.read_text(); schema=schema_p.read_text(); pkg=json.loads(pkg_p.read_text()); css=css_p.read_text()
pkg['version']='0.17.0';pkg_p.write_text(json.dumps(pkg,ensure_ascii=False,indent=2)+'\n')
server=re.sub(r"version: '[^']+'","version: '0.17.0'",server,count=1)

# Pricing catalog is public configuration, not a secret.
if 'const pricingCatalog=' not in server:
    anchor="function stripePriceFor(scope,cycle){"
    catalog=r'''const pricingCatalog={
  private_free:{code:'private_free',scope:'private',name:'Privat Free',monthly:0,yearly:0,maxCases:5},
  private_pro:{code:'private_pro',scope:'private',name:'Privat Pro',monthly:4.99,yearly:49.99},
  management_starter:{code:'management_starter',scope:'organization',name:'Verwaltung Starter',monthly:29.99,yearly:299.99,maxMembers:3,maxProperties:25,maxUnits:25},
  management_pro:{code:'management_pro',scope:'organization',name:'Verwaltung Pro',monthly:59.99,yearly:599.99,maxMembers:5,maxProperties:100,maxUnits:100},
  management_business:{code:'management_business',scope:'organization',name:'Verwaltung Business',monthly:119.99,yearly:1199.99,maxMembers:10,maxProperties:300,maxUnits:300}
};
function publicPricingCatalog(){return Object.values(pricingCatalog)}
function stripePriceForPlan(planCode,cycle){
 const env={
  private_pro:{monthly:'STRIPE_PRICE_PRIVATE_PRO_MONTHLY',yearly:'STRIPE_PRICE_PRIVATE_PRO_YEARLY'},
  management_starter:{monthly:'STRIPE_PRICE_MANAGEMENT_STARTER_MONTHLY',yearly:'STRIPE_PRICE_MANAGEMENT_STARTER_YEARLY'},
  management_pro:{monthly:'STRIPE_PRICE_MANAGEMENT_PRO_MONTHLY',yearly:'STRIPE_PRICE_MANAGEMENT_PRO_YEARLY'},
  management_business:{monthly:'STRIPE_PRICE_MANAGEMENT_BUSINESS_MONTHLY',yearly:'STRIPE_PRICE_MANAGEMENT_BUSINESS_YEARLY'}
 };
 return process.env[env[planCode]?.[cycle]||'']||null;
}
function applyPlanLimits(planCode){const p=pricingCatalog[planCode];return p&&p.scope==='organization'?{maxMembers:p.maxMembers,maxProperties:p.maxProperties,maxUnits:p.maxUnits}:null}

'''
    server=server.replace(anchor,catalog+anchor)
# Keep old helper for compatibility but make it delegate to new variables when possible.
server=re.sub(r"function stripePriceFor\(scope,cycle\)\{.*?\n\}","function stripePriceFor(scope,cycle){return stripePriceForPlan(scope==='organization'?'management_pro':'private_pro',cycle)}",server,count=1,flags=re.S)

# public pricing endpoint
if "app.get('/api/pricing'" not in server:
    marker="app.get('/api/billing/plan', auth, async (req,res,next)=>{"
    server=server.replace(marker,"app.get('/api/pricing',(_req,res)=>res.json({plans:publicPricingCatalog(),trialDays:14,unitExplanation:'Eine Einheit ist eine separat verwaltete Wohnung oder Gewerbeeinheit.'}));\n\n"+marker)

# enrich billing plan response with catalog and exact configured plan status
server=server.replace("return res.json({scope:'organization',plan:{...org,...billingState(org)},usage,checkoutConfigured:Boolean(process.env.STRIPE_SECRET_KEY&&(process.env.STRIPE_PRICE_MANAGEMENT_MONTHLY||process.env.STRIPE_PRICE_MANAGEMENT_YEARLY)),cycles:{monthly:Boolean(process.env.STRIPE_PRICE_MANAGEMENT_MONTHLY),yearly:Boolean(process.env.STRIPE_PRICE_MANAGEMENT_YEARLY)}});",
"return res.json({scope:'organization',plan:{...org,...billingState(org)},usage,catalog:publicPricingCatalog().filter(p=>p.scope==='organization'),checkoutConfigured:Boolean(process.env.STRIPE_SECRET_KEY),cycles:{monthly:true,yearly:true}});")
server=server.replace("res.json({scope:'private',plan:r.rows[0],checkoutConfigured:Boolean(process.env.STRIPE_SECRET_KEY&&(process.env.STRIPE_PRICE_PRIVATE_MONTHLY||process.env.STRIPE_PRICE_PRIVATE_YEARLY)),cycles:{monthly:Boolean(process.env.STRIPE_PRICE_PRIVATE_MONTHLY),yearly:Boolean(process.env.STRIPE_PRICE_PRIVATE_YEARLY)}});",
"res.json({scope:'private',plan:r.rows[0],catalog:publicPricingCatalog().filter(p=>p.scope==='private'),checkoutConfigured:Boolean(process.env.STRIPE_SECRET_KEY),cycles:{monthly:true,yearly:true}});")

# checkout chooses an explicit plan; server validates scope and configured price id.
old="const scope=org?'organization':'private';const cycle=req.body.cycle==='yearly'?'yearly':'monthly';const price=stripePriceFor(scope,cycle);if(!process.env.STRIPE_SECRET_KEY||!price)return res.status(503).json({error:'Online-Zahlung ist noch nicht vollständig konfiguriert.'});"
new="const scope=org?'organization':'private';const cycle=req.body.cycle==='yearly'?'yearly':'monthly';const planCode=cleanText(req.body.planCode,80)||(org?'management_pro':'private_pro');const selected=pricingCatalog[planCode];if(!selected||selected.scope!==scope||selected.monthly===0)return res.status(400).json({error:'Ungültiger Tarif.'});const price=stripePriceForPlan(planCode,cycle);if(!process.env.STRIPE_SECRET_KEY||!price)return res.status(503).json({error:'Online-Zahlung ist für diesen Tarif noch nicht vollständig konfiguriert.'});"
server=server.replace(old,new)
server=server.replace("'metadata[scope]':scope};","'metadata[scope]':scope,'metadata[plan_code]':planCode};")

# Store plan code and limits as soon as checkout completes/subscription webhook arrives.
server=server.replace("const orgId=s.metadata?.organization_id||null,userId=s.metadata?.user_id||null;","const orgId=s.metadata?.organization_id||null,userId=s.metadata?.user_id||null,planCode=s.metadata?.plan_code||null;")
server=server.replace("if(orgId)await pool.query(`UPDATE organizations SET subscription_provider='stripe',subscription_customer_id=$2,subscription_id=$3 WHERE id=$1`,[orgId,String(s.customer||''),String(s.subscription||'')]);",
"if(orgId){const lim=applyPlanLimits(planCode);await pool.query(`UPDATE organizations SET subscription_provider='stripe',subscription_customer_id=$2,subscription_id=$3,plan_code=COALESCE($4,plan_code),max_members=COALESCE($5,max_members),max_properties=COALESCE($6,max_properties),max_units=COALESCE($7,max_units) WHERE id=$1`,[orgId,String(s.customer||''),String(s.subscription||''),planCode,lim?.maxMembers,lim?.maxProperties,lim?.maxUnits]);}")
server=server.replace("if(userId)await pool.query(`UPDATE users SET subscription_provider='stripe',subscription_customer_id=$2,subscription_id=$3 WHERE id=$1`,[userId,String(s.customer||''),String(s.subscription||'')]);",
"if(userId)await pool.query(`UPDATE users SET subscription_provider='stripe',subscription_customer_id=$2,subscription_id=$3,plan_code=COALESCE($4,plan_code) WHERE id=$1`,[userId,String(s.customer||''),String(s.subscription||''),planCode]);")

# New management workspace: neutral trial based on Pro capacity, 14 days.
server=server.replace("VALUES ($1,$2,'business_trial',$3,'trialing',now()+interval '14 days',5,25,250)","VALUES ($1,$2,'management_trial',$3,'trialing',now()+interval '14 days',5,100,100)")
server=server.replace("plan_code: 'business_trial'","plan_code: 'management_trial'")
server_p.write_text(server)

# schema defaults / comments for clarity
if '-- v0.17 pricing catalog' not in schema:
    schema += "\n-- v0.17 pricing catalog is defined in application code; management trials start with Pro-sized limits and are converted to paid plan limits after checkout.\n"
schema_p.write_text(schema)

old_pricing='''        <section className="pricingSection" id="tarife">
          <div className="sectionIntro"><span>TARIFE</span><h2>Für den einzelnen Mieter. Und für ganze Verwaltungen.</h2><p>MängelFix bekommt zwei klar getrennte Produktlinien. Die konkreten Preise legen wir vor dem Zahlungsstart fest.</p></div>
          <div className="pricingGrid">
            <article className="pricingCard privatePlan"><div className="planTag">PRIVAT</div><h3>MängelFix Privat</h3><p className="planLead">Für Mieter und private Nutzer, die ihre eigenen Vorgänge sauber dokumentieren möchten.</p><div className="planPrice"><strong>Einzeltarif</strong><span>1 persönliches Konto</span></div><ul><li>Eigene Mängel & Objekte</li><li>Fotos, Fristen und Verlauf</li><li>Professionelle PDF-Dokumentation</li><li>Persönliches Absenderprofil</li></ul><button onClick={() => navigate(user ? '/app' : '/registrieren')}>{user ? 'Zur App' : 'Privat starten'} →</button></article>
            <article className="pricingCard businessPlan"><div className="planTag">HAUSVERWALTUNG</div><h3>MängelFix Verwaltung</h3><p className="planLead">Für Hausverwaltungen, Vermieterbüros und Teams, die gemeinsam an Objekten und Vorgängen arbeiten.</p><div className="planPrice"><strong>Teamtarif</strong><span>Mehrere Mitarbeiterkonten</span></div><ul><li>Gemeinsamer Arbeitsbereich</li><li>Inhaber-, Admin- und Mitarbeiterrollen</li><li>Mitarbeiter selbst anlegen</li><li>Gemeinsamer Zugriff auf Mängel & Dokumente</li><li>Für viele Objekte skalierbar</li></ul><button onClick={() => navigate(user ? '/app' : '/registrieren')}>{user ? 'Team einrichten' : 'Verwaltung starten'} →</button></article>
          </div>
        </section>'''
new_pricing='''        <section className="pricingSection" id="tarife">
          <div className="sectionIntro"><span>TARIFE</span><h2>Einfach für Privat. Planbar für Verwaltungen.</h2><p>Privat funktioniert MängelFix auch ohne verknüpfte Hausverwaltung. Verwaltungen zahlen nach der Zahl ihrer verwalteten Einheiten – nicht nach der Zahl der gemeldeten Mängel.</p></div>
          <div className="pricingExplain"><b>Was bedeutet „Einheit“?</b><p>Eine Einheit ist eine separat verwaltete Wohnung oder Gewerbeeinheit. Beispiel: 3 Häuser mit jeweils 8 Wohnungen = 24 Einheiten. Wie viele Mängel dort gemeldet werden, spielt für den Tarif keine Rolle.</p></div>
          <div className="pricingPrivateRow">
            <article className="pricingCard privatePlan"><div className="planTag">PRIVAT FREE</div><h3>Kostenlos starten</h3><p className="planLead">Für gelegentliche Mängel und zum Kennenlernen.</p><div className="planPrice"><strong>0 €</strong><span>dauerhaft kostenlos</span></div><ul><li>Grundlegende Mängelerfassung</li><li>Fotos und Verlauf</li><li>Manueller Empfänger – keine Verwaltung muss MängelFix nutzen</li><li>Bis zu 5 aktive Vorgänge</li></ul><button onClick={() => navigate(user ? '/app' : '/registrieren')}>{user ? 'Zur App' : 'Kostenlos starten'} →</button></article>
            <article className="pricingCard privatePlan featuredPlan"><div className="planTag">PRIVAT PRO</div><h3>Mehr Funktionen für deine Fälle</h3><p className="planLead">Für regelmäßige Reklamationen, Liefer-, Produkt-, Dienstleistungs-, Fahrzeug-, Reise- und Mietmängel.</p><div className="planPrice"><strong>4,99 €</strong><span>/ Monat · oder 49,99 € / Jahr</span></div><ul><li>Unbegrenzte Vorgänge</li><li>Erweiterte Belege & Dokumentation</li><li>Fristen, Aufgaben und Termine</li><li>Übergabe-/Abnahmeprotokolle</li><li>Erweiterte PDFs, Archiv und Auswertungen</li></ul><button onClick={() => navigate(user ? '/app' : '/registrieren')}>{user ? 'Pro ansehen' : 'Privat Pro starten'} →</button></article>
          </div>
          <div className="managementPricingIntro"><span>HAUSVERWALTUNG</span><h3>14 Tage kostenlos testen</h3><p>Alle Verwaltungsfunktionen kennenlernen. Danach den passenden Tarif nach verwalteten Einheiten wählen.</p></div>
          <div className="managementPricingGrid">
            <article className="pricingCard businessPlan"><div className="planTag">STARTER</div><h3>Bis 25 Einheiten</h3><div className="planPrice"><strong>29,99 €</strong><span>/ Monat · 299,99 € / Jahr</span></div><ul><li>Bis 3 Mitarbeiter</li><li>Mieter-Verknüpfungen optional</li><li>Aufgaben, Kalender & Fristen</li><li>Handwerker-/Dienstleisterprozess</li><li>Übergabe- und Mängelprotokolle</li></ul></article>
            <article className="pricingCard businessPlan featuredPlan"><div className="planTag">PRO</div><h3>Bis 100 Einheiten</h3><div className="planPrice"><strong>59,99 €</strong><span>/ Monat · 599,99 € / Jahr</span></div><ul><li>Bis 5 Mitarbeiter</li><li>Alles aus Starter</li><li>Qualitätsdashboard & Analysen</li><li>Audit-Log und Teamsteuerung</li><li>Für wachsende Verwaltungen</li></ul></article>
            <article className="pricingCard businessPlan"><div className="planTag">BUSINESS</div><h3>Bis 300 Einheiten</h3><div className="planPrice"><strong>119,99 €</strong><span>/ Monat · 1.199,99 € / Jahr</span></div><ul><li>Bis 10 Mitarbeiter</li><li>Alles aus Pro</li><li>Größere Portfolios</li><li>Zentrale Aufgaben- und Terminsteuerung</li><li>Priorisierte Produktbasis für professionelle Teams</li></ul></article>
          </div>
          <div className="enterpriseNote"><b>Mehr als 300 Einheiten?</b><span>Individuelles Angebot – damit große Bestände nicht in ein unpassendes Standardpaket gezwungen werden.</span></div>
          <button className="managementStartButton" onClick={() => navigate(user ? '/app' : '/registrieren')}>{user ? 'Verwaltung einrichten' : '14 Tage kostenlos testen'} →</button>
        </section>'''
if old_pricing not in app: raise SystemExit('pricing block not found')
app=app.replace(old_pricing,new_pricing)
app_p.write_text(app)
css += '''\n/* v0.17 pricing */\n.pricingExplain{max-width:850px;margin:0 auto 28px;padding:18px 20px;border:1px solid #dce3e7;border-radius:12px;background:#f7f9fa}.pricingExplain b{display:block;margin-bottom:5px}.pricingExplain p{margin:0;color:#5f6b74}.pricingPrivateRow{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-bottom:42px}.managementPricingIntro{text-align:center;margin:34px 0 18px}.managementPricingIntro>span{font-size:11px;font-weight:800;letter-spacing:.13em;color:#67737c}.managementPricingIntro h3{font-size:26px;margin:7px 0}.managementPricingGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.featuredPlan{border:2px solid #18212b;transform:translateY(-5px);box-shadow:0 12px 30px rgba(24,33,43,.10)}.enterpriseNote{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin:24px 0 18px;color:#5f6b74}.enterpriseNote b{color:#18212b}.managementStartButton{display:block;margin:0 auto}.pricingCard .planPrice strong{font-size:28px}.pricingCard .planPrice span{display:block;margin-top:4px}@media(max-width:900px){.managementPricingGrid{grid-template-columns:1fr}.featuredPlan{transform:none}}@media(max-width:680px){.pricingPrivateRow{grid-template-columns:1fr}}\n'''
css_p.write_text(css)
print('v0.17 pricing prepared')
