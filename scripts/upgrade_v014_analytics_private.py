from pathlib import Path
import json,re
root=Path('.')
schema_p=root/'server/schema.sql'; server_p=root/'server/index.js'; app_p=root/'client/src/App.jsx'; css_p=root/'client/src/maengelfix-pro.css'; pkg_p=root/'server/package.json'
schema=schema_p.read_text(); server=server_p.read_text(); app=app_p.read_text(); css=css_p.read_text(); pkg=json.loads(pkg_p.read_text())

if '-- v0.14: allgemeine Privatmängel und Qualitätsanalyse' not in schema:
    schema += r'''

-- v0.14: allgemeine Privatmängel und Qualitätsanalyse
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS case_context text NOT NULL DEFAULT 'housing';
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS reference_label text;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS subject_label text;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS counterparty_type text;
CREATE INDEX IF NOT EXISTS defect_cases_context_idx ON defect_cases(user_id,case_context,created_at DESC);
'''
schema_p.write_text(schema)
pkg['version']='0.14.0'; pkg_p.write_text(json.dumps(pkg,ensure_ascii=False,indent=2)+'\n')
server=re.sub(r"res\.json\(\{ ok: true, service: 'maengelfix', version: '[^']+'[^}]*\}\);","res.json({ ok: true, service: 'maengelfix', version: '0.14.0', mail: smtpConfigured ? 'smtp' : 'manual' });",server,count=1)

# Extend case create and update safely.
old_cols="(id,user_id,organization_id,property_id,unit_id,tenant_link_id,submitted_by_tenant,title,category,description,property_label,location_label,discovered_on,recipient_name,recipient_email,recipient_address,deadline_on,status)"
new_cols="(id,user_id,organization_id,property_id,unit_id,tenant_link_id,submitted_by_tenant,title,category,description,property_label,location_label,discovered_on,recipient_name,recipient_email,recipient_address,deadline_on,case_context,reference_label,subject_label,counterparty_type,status)"
if old_cols in server:
    server=server.replace(old_cols,new_cols,1)
old_vals="VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,'draft')"
new_vals="VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,'draft')"
if old_vals in server:
    server=server.replace(old_vals,new_vals,1)
needle="req.body.deadlineOn || null\n      ]"
if needle in server:
    server=server.replace(needle,"req.body.deadlineOn || null,\n        ['housing','delivery','product','service','vehicle','travel','other'].includes(req.body.caseContext)?req.body.caseContext:'housing',\n        cleanText(req.body.referenceLabel,180),\n        cleanText(req.body.subjectLabel,220),\n        cleanText(req.body.counterpartyType,80)\n      ]",1)

# Analytics APIs.
anchor="app.get('/api/cases', auth, async (req, res, next) => {"
if "app.get('/api/analytics'" not in server:
    endpoints=r'''
app.get('/api/analytics',auth,async(req,res,next)=>{try{
 const org=await organizationForUser(req.user.id);
 if(org){
  const [summary,cats,properties,trend,providers]=await Promise.all([
   pool.query(`SELECT count(*)::int total,count(*) FILTER(WHERE status<>'resolved')::int open,count(*) FILTER(WHERE status='resolved')::int resolved,count(*) FILTER(WHERE deadline_on<current_date AND status<>'resolved')::int overdue,round(avg(EXTRACT(EPOCH FROM (updated_at-created_at))/86400) FILTER(WHERE status='resolved')::numeric,1) avg_days FROM defect_cases WHERE organization_id=$1`,[org.id]),
   pool.query(`SELECT category,count(*)::int total,count(*) FILTER(WHERE status<>'resolved')::int open FROM defect_cases WHERE organization_id=$1 GROUP BY category ORDER BY total DESC LIMIT 8`,[org.id]),
   pool.query(`SELECT COALESCE(p.name,c.property_label,'Ohne Objekt') label,count(*)::int total,count(*) FILTER(WHERE c.status<>'resolved')::int open,count(*) FILTER(WHERE c.deadline_on<current_date AND c.status<>'resolved')::int overdue FROM defect_cases c LEFT JOIN properties p ON p.id=c.property_id WHERE c.organization_id=$1 GROUP BY COALESCE(p.name,c.property_label,'Ohne Objekt') ORDER BY open DESC,total DESC LIMIT 8`,[org.id]),
   pool.query(`SELECT to_char(date_trunc('month',created_at),'YYYY-MM') month,count(*)::int total,count(*) FILTER(WHERE status='resolved')::int resolved FROM defect_cases WHERE organization_id=$1 AND created_at>=date_trunc('month',now())-interval '5 months' GROUP BY 1 ORDER BY 1`,[org.id]),
   pool.query(`SELECT sp.company_name,count(wo.*)::int orders,round(avg(EXTRACT(EPOCH FROM (COALESCE(wo.accepted_at,wo.updated_at)-wo.created_at))/3600)::numeric,1) response_hours,count(*) FILTER(WHERE wo.status='completed')::int completed FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id WHERE wo.organization_id=$1 GROUP BY sp.id,sp.company_name HAVING count(wo.*)>0 ORDER BY orders DESC LIMIT 6`,[org.id])
  ]);
  return res.json({scope:'organization',summary:summary.rows[0],categories:cats.rows,properties:properties.rows,trend:trend.rows,providers:providers.rows});
 }
 const [summary,contexts,cats,trend]=await Promise.all([
  pool.query(`SELECT count(*)::int total,count(*) FILTER(WHERE status<>'resolved')::int open,count(*) FILTER(WHERE status='resolved')::int resolved,count(*) FILTER(WHERE deadline_on<current_date AND status<>'resolved')::int overdue FROM defect_cases WHERE user_id=$1 AND organization_id IS NULL`,[req.user.id]),
  pool.query(`SELECT case_context,count(*)::int total,count(*) FILTER(WHERE status<>'resolved')::int open FROM defect_cases WHERE user_id=$1 AND organization_id IS NULL GROUP BY case_context ORDER BY total DESC`,[req.user.id]),
  pool.query(`SELECT category,count(*)::int total FROM defect_cases WHERE user_id=$1 AND organization_id IS NULL GROUP BY category ORDER BY total DESC LIMIT 8`,[req.user.id]),
  pool.query(`SELECT to_char(date_trunc('month',created_at),'YYYY-MM') month,count(*)::int total,count(*) FILTER(WHERE status='resolved')::int resolved FROM defect_cases WHERE user_id=$1 AND organization_id IS NULL AND created_at>=date_trunc('month',now())-interval '5 months' GROUP BY 1 ORDER BY 1`,[req.user.id])
 ]);
 res.json({scope:'private',summary:summary.rows[0],contexts:contexts.rows,categories:cats.rows,trend:trend.rows});
}catch(e){next(e)}});
'''
    server=server.replace(anchor,endpoints+anchor)
server_p.write_text(server)

# Client general private case types and analytics.
app=app.replace("const categories = ['Feuchtigkeit / Schimmel', 'Heizung / Warmwasser', 'Sanitär', 'Elektro', 'Fenster / Türen', 'Boden / Wand', 'Lärm', 'Außenbereich', 'Sonstiges'];", "const categories = ['Feuchtigkeit / Schimmel','Heizung / Warmwasser','Sanitär','Elektro','Fenster / Türen','Boden / Wand','Beschädigung','Fehlteil / unvollständig','Funktionsmangel','Qualitätsmangel','Falsche Lieferung / Ausführung','Lärm','Außenbereich','Sonstiges'];\nconst caseContexts={housing:{label:'Wohnen / Miete',subject:'Objekt / Wohnung',place:'Raum / Ort',recipient:'Vermieter / Hausverwaltung',reference:'Miet-/Objektbezug'},delivery:{label:'Lieferung',subject:'Produkt / Lieferung',place:'Schaden / Fundstelle',recipient:'Händler / Lieferdienst',reference:'Bestell- / Sendungsnummer'},product:{label:'Produkt / Kauf',subject:'Produkt',place:'Variante / Seriennummer',recipient:'Händler / Hersteller',reference:'Bestell- / Rechnungsnummer'},service:{label:'Dienstleistung / Handwerker',subject:'Auftrag / Leistung',place:'Ausführungsort',recipient:'Firma / Dienstleister',reference:'Auftrags- / Rechnungsnummer'},vehicle:{label:'Fahrzeug / Werkstatt',subject:'Fahrzeug / Leistung',place:'Bauteil / Bereich',recipient:'Werkstatt / Verkäufer',reference:'Auftrag / Rechnung / Kennzeichen'},travel:{label:'Reise / Unterkunft',subject:'Buchung / Unterkunft',place:'Zimmer / Ort',recipient:'Anbieter / Unterkunft',reference:'Buchungsnummer'},other:{label:'Sonstiger Mangel',subject:'Sache / Leistung',place:'Ort / Bereich',recipient:'Ansprechpartner / Firma',reference:'Referenz / Vorgangsnummer'}};")

app=app.replace("useState({ title: '', category: categories[0], description: '', propertyLabel: '', locationLabel: '', discoveredOn: today, recipientName: '', recipientEmail: '', recipientAddress: '', deadlineOn: '', destinationLinkId: '' })", "useState({ title:'',caseContext:'housing',category:categories[0],description:'',propertyLabel:'',locationLabel:'',subjectLabel:'',referenceLabel:'',counterpartyType:'',discoveredOn:today,recipientName:'',recipientEmail:'',recipientAddress:'',deadlineOn:'',destinationLinkId:'' })")
old="<div className=\"formGrid two\"><label>Titel<input required placeholder=\"z. B. Heizung bleibt kalt\" value={form.title} onChange={e => field('title', e.target.value)} /></label><label>Kategorie<select value={form.category} onChange={e => field('category', e.target.value)}>{categories.map(item => <option key={item}>{item}</option>)}</select></label></div>"
new="<label>Worum geht es bei diesem Mangel?<select value={form.caseContext} onChange={e=>field('caseContext',e.target.value)}>{Object.entries(caseContexts).map(([k,v])=><option key={k} value={k}>{v.label}</option>)}</select></label><div className=\"formGrid two\"><label>Titel<input required placeholder={form.caseContext==='housing'?'z. B. Heizung bleibt kalt':'z. B. Lieferung beschädigt angekommen'} value={form.title} onChange={e => field('title', e.target.value)} /></label><label>Kategorie<select value={form.category} onChange={e => field('category', e.target.value)}>{categories.map(item => <option key={item}>{item}</option>)}</select></label></div>"
app=app.replace(old,new)
old2="<div className=\"formGrid two\"><label>Objekt<input placeholder=\"z. B. Wohnung, Musterstraße 12\" value={form.propertyLabel} onChange={e => field('propertyLabel', e.target.value)} /></label><label>Raum / Ort<input placeholder=\"z. B. Badezimmer\" value={form.locationLabel} onChange={e => field('locationLabel', e.target.value)} /></label><label>Festgestellt am<input type=\"date\" value={form.discoveredOn} onChange={e => field('discoveredOn', e.target.value)} /></label><label>Rückmeldung bis<input type=\"date\" value={form.deadlineOn} onChange={e => field('deadlineOn', e.target.value)} /></label></div>"
new2="<div className=\"formGrid two\"><label>{caseContexts[form.caseContext].subject}<input placeholder={form.caseContext==='housing'?'z. B. Wohnung, Musterstraße 12':'Was ist konkret betroffen?'} value={form.subjectLabel||form.propertyLabel} onChange={e=>{field('subjectLabel',e.target.value);field('propertyLabel',e.target.value)}} /></label><label>{caseContexts[form.caseContext].place}<input value={form.locationLabel} onChange={e=>field('locationLabel',e.target.value)} /></label><label>{caseContexts[form.caseContext].reference}<input value={form.referenceLabel} onChange={e=>field('referenceLabel',e.target.value)} /></label><label>Festgestellt am<input type=\"date\" value={form.discoveredOn} onChange={e => field('discoveredOn', e.target.value)} /></label><label>Rückmeldung / Frist bis<input type=\"date\" value={form.deadlineOn} onChange={e => field('deadlineOn', e.target.value)} /></label></div>"
app=app.replace(old2,new2)
app=app.replace("<div className=\"subSection\"><h3>{form.destinationLinkId?'Zusätzlicher Empfänger (optional)':'Empfänger'}</h3><p className=\"muted\">Optional – Hausverwaltung, Vermieter oder anderer Ansprechpartner.</p></div>","<div className=\"subSection\"><h3>{form.destinationLinkId?'Zusätzlicher Empfänger (optional)':caseContexts[form.caseContext].recipient}</h3><p className=\"muted\">Optional – die Stelle, an die du den Mangel melden oder dokumentieren möchtest.</p></div>")

component_anchor="function BillingView(){"
if 'function AnalyticsView(' not in app:
    comp=r'''
const analyticsContextLabels={housing:'Wohnen / Miete',delivery:'Lieferung',product:'Produkt / Kauf',service:'Dienstleistung',vehicle:'Fahrzeug / Werkstatt',travel:'Reise / Unterkunft',other:'Sonstiges'};
function AnalyticsView(){
 const [data,setData]=useState(null);const [error,setError]=useState('');useEffect(()=>{api('/api/analytics').then(setData).catch(e=>setError(e.message))},[]);if(!data)return <div className="workspacePage"><div className="emptyCard">Auswertung wird geladen…</div></div>;const s=data.summary||{};const max=Math.max(1,...(data.categories||[]).map(x=>x.total));return <div className="workspacePage analyticsPage"><div className="workspaceHeading"><div><span>{data.scope==='organization'?'QUALITÄT & MÄNGELANALYSE':'MEINE MÄNGEL'}</span><h1>{data.scope==='organization'?'Qualitätsdashboard':'Persönliche Auswertung'}</h1><p>{data.scope==='organization'?'Erkenne Problemobjekte, häufige Mangelarten und Bearbeitungsengpässe.':'Sieh, in welchen Bereichen du Mängel dokumentiert hast und was noch offen ist.'}</p></div></div>{error&&<div className="errorBox">{error}</div>}<div className="analyticsMetrics"><article><span>GESAMT</span><b>{s.total||0}</b></article><article><span>OFFEN</span><b>{s.open||0}</b></article><article className="danger"><span>ÜBERFÄLLIG</span><b>{s.overdue||0}</b></article><article><span>ERLEDIGT</span><b>{s.resolved||0}</b></article>{data.scope==='organization'&&<article><span>Ø BEARBEITUNG</span><b>{s.avg_days||'—'} <small>Tage</small></b></article>}</div><div className="analyticsGrid"><section className="workspacePanel"><div className="panelHead"><div><span>MANGELARTEN</span><h2>Häufigste Kategorien</h2></div></div><div className="analyticsBars">{(data.categories||[]).map(x=><div key={x.category}><span><b>{x.category}</b><em>{x.total}</em></span><i><u style={{width:`${Math.max(5,x.total/max*100)}%`}}/></i></div>)}</div></section>{data.scope==='organization'?<section className="workspacePanel"><div className="panelHead"><div><span>OBJEKTE</span><h2>Wo häufen sich offene Mängel?</h2></div></div><div className="analyticsList">{(data.properties||[]).map(x=><div key={x.label}><span><b>{x.label}</b><small>{x.total} insgesamt</small></span><strong>{x.open} offen{x.overdue?` · ${x.overdue} überfällig`:''}</strong></div>)}</div></section>:<section className="workspacePanel"><div className="panelHead"><div><span>ANWENDUNGSBEREICHE</span><h2>Wofür nutzt du MängelFix?</h2></div></div><div className="analyticsList">{(data.contexts||[]).map(x=><div key={x.case_context}><span><b>{analyticsContextLabels[x.case_context]||x.case_context}</b><small>{x.total} Vorgänge</small></span><strong>{x.open} offen</strong></div>)}</div></section>}</div>{data.scope==='organization'&&<section className="workspacePanel analyticsProviders"><div className="panelHead"><div><span>DIENSTLEISTER</span><h2>Reaktion auf Arbeitsaufträge</h2></div></div><div className="analyticsList">{(data.providers||[]).length?data.providers.map(x=><div key={x.company_name}><span><b>{x.company_name}</b><small>{x.orders} Aufträge · {x.completed} erledigt</small></span><strong>{x.response_hours??'—'} Std. Ø Reaktion</strong></div>):<div className="emptyMini">Noch nicht genug Arbeitsaufträge für eine Auswertung.</div>}</div></section>}</div>;
}

'''
    app=app.replace(component_anchor,comp+component_anchor)
app=app.replace("else if (view === 'inspections') content = <InspectionsView onSelectCase={setSelected} />;","else if (view === 'analytics') content = <AnalyticsView />;\n  else if (view === 'inspections') content = <InspectionsView onSelectCase={setSelected} />;")
# Sidebar analytics after overview.
needle="<button className={view === 'cases' || selected ? 'active' : ''} onClick={() => { setSelected(null); setView('cases'); }}><span>M</span>Mängel"
if needle in app and "setView('analytics')" not in app:
    app=app.replace(needle,"<button className={view === 'analytics' ? 'active' : ''} onClick={() => { setSelected(null); setView('analytics'); }}><span>Q</span>{management?.organization?'Analyse':'Auswertung'}</button>"+needle)
# Detail labels become context aware for private use.
app=app.replace("<div><span>Objekt</span><b>{item.property_label || '—'}</b></div><div><span>Raum / Ort</span><b>{item.location_label || '—'}</b></div>","<div><span>{data.viewerRole==='management'?'Objekt':(caseContexts[item.case_context||'housing']?.subject||'Bezug')}</span><b>{item.subject_label||item.property_label||'—'}</b></div><div><span>{data.viewerRole==='management'?'Raum / Ort':(caseContexts[item.case_context||'housing']?.place||'Ort / Bereich')}</span><b>{item.location_label||'—'}</b></div>")
app_p.write_text(app)

css += r'''
/* v0.14 Qualitätsanalyse & allgemeine Privatmängel */
.analyticsMetrics{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:18px 0}.analyticsMetrics article{background:#fff;border:1px solid #dce2e5;border-radius:12px;padding:17px}.analyticsMetrics span{display:block;font-size:10px;font-weight:800;letter-spacing:.1em;color:#73808a}.analyticsMetrics b{display:block;font-size:27px;margin-top:5px}.analyticsMetrics b small{font-size:12px}.analyticsMetrics .danger b{color:#b42318}.analyticsGrid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.analyticsBars{display:grid;gap:13px}.analyticsBars>div>span{display:flex;justify-content:space-between;gap:12px;margin-bottom:5px}.analyticsBars em{font-style:normal;font-weight:800}.analyticsBars i{display:block;height:8px;background:#edf0f2;border-radius:10px;overflow:hidden}.analyticsBars u{display:block;height:100%;background:#2457d6;border-radius:10px;text-decoration:none}.analyticsList{display:grid;gap:8px}.analyticsList>div{display:flex;justify-content:space-between;gap:18px;padding:12px 0;border-bottom:1px solid #e5e9eb}.analyticsList span b,.analyticsList span small{display:block}.analyticsList span small{color:#78838c;margin-top:3px}.analyticsList strong{text-align:right}.analyticsProviders{margin-top:16px}@media(max-width:900px){.analyticsMetrics{grid-template-columns:repeat(2,1fr)}.analyticsGrid{grid-template-columns:1fr}}@media(max-width:560px){.analyticsMetrics{grid-template-columns:1fr 1fr}.analyticsList>div{flex-direction:column}.analyticsList strong{text-align:left}}
'''
css_p.write_text(css)
print('v0.14 analytics/private upgrade prepared')
