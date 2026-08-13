from pathlib import Path
import json,re
root=Path('.')
server_p=root/'server/index.js'; app_p=root/'client/src/App.jsx'; css_p=root/'client/src/maengelfix-pro.css'; pkg_p=root/'server/package.json'
server=server_p.read_text();app=app_p.read_text();css=css_p.read_text();pkg=json.loads(pkg_p.read_text())
pkg['version']='0.16.0';pkg_p.write_text(json.dumps(pkg,ensure_ascii=False,indent=2)+'\n')
server=re.sub(r"res\.json\(\{ ok: true, service: 'maengelfix', version: '[^']+'", "res.json({ ok: true, service: 'maengelfix', version: '0.16.0'",server,count=1)

# Replace compact legacy account export with comprehensive, user-scoped export.
pat=re.compile(r"app\.get\('/api/account/export', auth, async \(req,res,next\)=>\{.*?\n\}\);",re.S)
m=pat.search(server)
if m:
    replacement=r'''app.get('/api/account/export', auth, async (req,res,next)=>{
  try {
    const queries={
      account: pool.query(`SELECT id,name,email,street,postal_code,city,country,phone,email_verified_at,plan_code,subscription_status,subscription_provider,subscription_current_period_end,created_at FROM users WHERE id=$1`,[req.user.id]),
      cases: pool.query(`SELECT * FROM defect_cases WHERE user_id=$1 ORDER BY created_at`,[req.user.id]),
      attachments: pool.query(`SELECT a.id,a.case_id,a.original_name,a.mime_type,a.size_bytes,a.evidence_type,a.note,a.captured_at,a.source,a.created_at FROM attachments a WHERE a.user_id=$1 ORDER BY a.created_at`,[req.user.id]),
      caseEvents: pool.query(`SELECT id,case_id,event_type,note,visibility,created_at FROM case_events WHERE user_id=$1 ORDER BY created_at`,[req.user.id]),
      messages: pool.query(`SELECT id,case_id,message,created_at FROM case_messages WHERE user_id=$1 ORDER BY created_at`,[req.user.id]),
      tasks: pool.query(`SELECT * FROM case_tasks WHERE created_by=$1 OR assigned_user_id=$1 ORDER BY created_at`,[req.user.id]),
      calendar: pool.query(`SELECT * FROM calendar_events WHERE created_by=$1 OR assigned_user_id=$1 ORDER BY starts_at`,[req.user.id]),
      inspections: pool.query(`SELECT * FROM inspection_protocols WHERE created_by=$1 ORDER BY created_at`,[req.user.id]),
      findings: pool.query(`SELECT f.* FROM inspection_findings f WHERE f.created_by=$1 ORDER BY f.created_at`,[req.user.id]),
      tenantLinks: pool.query(`SELECT tl.id,tl.status,tl.created_at,tl.disconnected_at,o.name organization,p.name property,u.label unit FROM tenant_links tl JOIN organizations o ON o.id=tl.organization_id JOIN properties p ON p.id=tl.property_id JOIN units u ON u.id=tl.unit_id WHERE tl.user_id=$1 ORDER BY tl.created_at`,[req.user.id]),
      organizations: pool.query(`SELECT om.organization_id,o.name,om.role,COALESCE(om.active,true) active,om.created_at FROM organization_memberships om JOIN organizations o ON o.id=om.organization_id WHERE om.user_id=$1 ORDER BY om.created_at`,[req.user.id]),
      notifications: pool.query(`SELECT id,type,title,body,link,read_at,created_at FROM notifications WHERE user_id=$1 ORDER BY created_at`,[req.user.id]),
      workOrders: pool.query(`SELECT wo.* FROM work_orders wo WHERE wo.created_by=$1 ORDER BY wo.created_at`,[req.user.id]),
      auditEntries: pool.query(`SELECT id,organization_id,case_id,action,entity_type,entity_id,summary,metadata,created_at FROM audit_logs WHERE user_id=$1 ORDER BY created_at`,[req.user.id]),
      billingEvents: pool.query(`SELECT id,provider,event_type,created_at FROM billing_events WHERE user_id=$1 ORDER BY created_at`,[req.user.id])
    };
    const keys=Object.keys(queries),values=await Promise.all(Object.values(queries));const payload={exportedAt:new Date().toISOString(),formatVersion:'1.0'};keys.forEach((k,i)=>payload[k]=k==='account'?(values[i].rows[0]||null):values[i].rows);
    res.setHeader('Content-Type','application/json; charset=utf-8');res.setHeader('Content-Disposition','attachment; filename="maengelfix-datenexport.json"');res.send(JSON.stringify(payload,null,2));
  } catch(error){next(error)}
});'''
    server=server[:m.start()]+replacement+server[m.end():]

# Tenant/private linked-management dashboard.
anchor="app.get('/api/tenant-links', auth, async (req,res,next)=>{"
if "app.get('/api/tenant-dashboard'" not in server:
    endpoint=r'''app.get('/api/tenant-dashboard',auth,async(req,res,next)=>{try{
 const [links,cases]=await Promise.all([
  pool.query(`SELECT tl.id,tl.status,tl.created_at,o.name organization_name,p.name property_name,p.street,p.postal_code,p.city,u.label unit_label,p.allow_tenant_submissions FROM tenant_links tl JOIN organizations o ON o.id=tl.organization_id JOIN properties p ON p.id=tl.property_id JOIN units u ON u.id=tl.unit_id WHERE tl.user_id=$1 AND tl.status='active' ORDER BY o.name,p.name,u.label`,[req.user.id]),
  pool.query(`SELECT c.id,c.title,c.category,c.status,c.deadline_on,c.updated_at,c.organization_id,c.property_label,c.location_label,o.name organization_name,(SELECT count(*)::int FROM case_messages m WHERE m.case_id=c.id) message_count,(SELECT count(*)::int FROM attachments a WHERE a.case_id=c.id) attachment_count FROM defect_cases c JOIN organizations o ON o.id=c.organization_id WHERE c.user_id=$1 AND c.submitted_by_tenant=true ORDER BY c.updated_at DESC`,[req.user.id])
 ]);res.json({links:links.rows,cases:cases.rows})
}catch(e){next(e)}});

'''
    server=server.replace(anchor,endpoint+anchor,1)
server_p.write_text(server)

# Legal pages updated to current product scope, integrations conditional in wording.
app=app.replace("['2. Welche Daten MängelFix verarbeitet', <p>Bei der Nutzung verarbeiten wir insbesondere Kontodaten wie Name und E-Mail-Adresse, freiwillige Profildaten wie Anschrift und Telefonnummer, die von dir erfassten Mängeldaten, Empfängerdaten, Fristen, Notizen sowie hochgeladene Fotos und technische Sitzungsdaten.</p>]", "['2. Welche Daten MängelFix verarbeitet', <p>Bei der Nutzung verarbeiten wir insbesondere Kontodaten, freiwillige Profildaten, erfasste Mängel- und Vorgangsdaten, Referenz- und Empfängerdaten, Fristen, Aufgaben, Termine, Nachrichten und Notizen sowie hochgeladene Fotos und Dokumente. Bei Verwaltungsarbeitsbereichen können außerdem Objekt-, Einheiten-, Mieter-, Dienstleister-, Arbeitsauftrags-, Übergabe- und Protokolldaten verarbeitet werden.</p>]")
app=app.replace("['3. Zweck und Rechtsgrundlage', <p>Die Daten werden verarbeitet, um dein Konto bereitzustellen, deine Vorgänge zu speichern, Dokumente zu erzeugen, Fotos zuzuordnen und die Anmeldung abzusichern. Soweit die Verarbeitung für die Bereitstellung des Dienstes erforderlich ist, erfolgt sie zur Durchführung des Nutzungsverhältnisses. Technisch erforderliche Sicherheitsmaßnahmen dienen außerdem dem sicheren und stabilen Betrieb.</p>]", "['3. Zweck und Rechtsgrundlage', <p>Die Daten werden verarbeitet, um Konten und Arbeitsbereiche bereitzustellen, Mängel zu dokumentieren und nachzuverfolgen, Kommunikation, Fristen, Termine und Arbeitsaufträge zu organisieren, Dokumente zu erzeugen und die Anmeldung abzusichern. Soweit dies für die Bereitstellung des Dienstes erforderlich ist, erfolgt die Verarbeitung zur Durchführung des Nutzungsverhältnisses. Technisch erforderliche Sicherheitsmaßnahmen dienen dem sicheren und stabilen Betrieb.</p>]")
app=app.replace("['6. Cookies und Anmeldung', <p>MängelFix verwendet ein technisch erforderliches Session-Cookie, damit du angemeldet bleibst. Es wird derzeit nicht für Werbung, Profilbildung oder Tracking verwendet.</p>]", "['6. Cookies, Anmeldung und PWA', <p>MängelFix verwendet ein technisch erforderliches Session-Cookie, damit du angemeldet bleibst. Die installierbare Web-App kann statische App-Ressourcen lokal zwischenspeichern; geschützte API-Inhalte und Seitennavigationen werden dabei nicht für Offline-Zwecke gecacht. Es findet dadurch kein Werbe- oder Profiling-Tracking statt.</p>]")
app=app.replace("['7. Speicherdauer', <p>Kontodaten und von dir angelegte Vorgänge werden grundsätzlich gespeichert, solange dein Konto besteht oder die Daten für die Bereitstellung des Dienstes benötigt werden. Löschanfragen kannst du an contact@kamilunavo.com richten, soweit keine gesetzlichen Aufbewahrungspflichten entgegenstehen.</p>]", "['7. Zahlungsabwicklung', <p>Sobald kostenpflichtige Tarife aktiviert werden, kann die Zahlungs- und Abonnementabwicklung über Stripe erfolgen. Zahlungsdaten werden dabei grundsätzlich beim Zahlungsdienstleister verarbeitet; MängelFix speichert für die Zuordnung insbesondere Kunden-, Abonnement-, Status- und Abrechnungsreferenzen. Vor Aktivierung kostenpflichtiger Tarife wird dieser Abschnitt bei Bedarf um die konkreten Anbieterangaben ergänzt.</p>],['8. Speicherdauer', <p>Kontodaten und von dir angelegte Vorgänge werden grundsätzlich gespeichert, solange dein Konto besteht oder die Daten für die Bereitstellung des Dienstes benötigt werden. In der App stehen Datenexport und Kontolöschung zur Verfügung. Gesetzliche Aufbewahrungspflichten können einer sofortigen Löschung einzelner Daten entgegenstehen.</p>]")
app=app.replace("['8. Deine Rechte'", "['9. Deine Rechte'").replace("['9. Sicherheit'", "['10. Sicherheit'").replace("['10. Stand'", "['11. Stand'")
app=app.replace("Stand: 12. August 2026. Diese Datenschutzerklärung", "Stand: 13. August 2026. Diese Datenschutzerklärung")
app=app.replace("['2. Leistungsumfang', <p>MängelFix unterstützt Nutzer beim Erfassen, Dokumentieren und Organisieren von Mängeln sowie beim Erstellen von PDF-Unterlagen. MängelFix ist kein Rechtsberatungsdienst und ersetzt keine individuelle rechtliche Prüfung.</p>]", "['2. Leistungsumfang', <p>MängelFix unterstützt private Nutzer beim allgemeinen Erfassen, Dokumentieren und Nachhalten von Mängeln, etwa bei Wohnen, Lieferungen, Produkten, Dienstleistungen, Fahrzeugen oder Reisen. Verwaltungsarbeitsbereiche sind auf Immobilien- und Mietmängel, Zuständigkeiten, Kommunikation, Dienstleister und Übergabe-/Abnahmeprotokolle ausgerichtet. MängelFix ist kein Rechtsberatungsdienst und ersetzt keine individuelle rechtliche Prüfung.</p>]")
app=app.replace("['4. Eigene Inhalte', <p>Nutzer sind für eingegebene Texte, Empfängerdaten und hochgeladene Bilder verantwortlich. Es dürfen keine rechtswidrigen Inhalte hochgeladen oder Rechte Dritter verletzt werden.</p>]", "['4. Eigene Inhalte und Belege', <p>Nutzer sind für eingegebene Texte, Empfänger- und Kontaktdaten sowie hochgeladene Bilder und Dokumente verantwortlich. Es dürfen nur für den jeweiligen Vorgang erforderliche Inhalte eingestellt werden; rechtswidrige Inhalte oder Verletzungen von Rechten Dritter sind unzulässig.</p>]")
app=app.replace("['8. Stand', <p>Stand: 12. August 2026.</p>]", "['8. Tarife und Zahlungen', <p>Kostenpflichtige Funktionen, Preise, Abrechnungszeiträume und Kündigungsmöglichkeiten werden vor dem verbindlichen Abschluss eines Abonnements angezeigt. Solange die Zahlungsfunktion nicht aktiviert ist, entsteht durch die bloße Nutzung einer Test- oder kostenlosen Version kein kostenpflichtiges Abonnement.</p>],['9. Stand', <p>Stand: 13. August 2026.</p>]")

# Private tenant connections view.
component_anchor="function SearchArchiveView({onSelect}){"
if 'function ConnectionsView(' not in app:
    comp=r'''function ConnectionsView({onSelect}){const [data,setData]=useState({links:[],cases:[]});const [error,setError]=useState('');useEffect(()=>{api('/api/tenant-dashboard').then(setData).catch(e=>setError(e.message))},[]);return <div className="workspacePage connectionsPage"><div className="workspaceHeading"><div><span>VERKNÜPFTE VERWALTUNGEN</span><h1>Meine digitalen Mietmängel</h1><p>Nur Mängel, die du ausdrücklich übermittelt hast, erscheinen hier bei der jeweiligen Verwaltung.</p></div></div>{error&&<div className="errorBox">{error}</div>}<div className="connectionCards">{data.links.map(l=><article key={l.id}><span>AKTIVE VERKNÜPFUNG</span><h2>{l.organization_name}</h2><p>{l.property_name} · {l.unit_label}</p><small>{[l.street,l.postal_code,l.city].filter(Boolean).join(', ')}</small><b>{l.allow_tenant_submissions?'Digitale Meldungen möglich':'Digitale Meldungen derzeit pausiert'}</b></article>)}</div><section className="workspacePanel"><div className="panelHead"><div><span>ÜBERMITTELTE MÄNGEL</span><h2>Bei Hausverwaltungen gemeldet</h2></div></div>{data.cases.length?data.cases.map(c=><button className="connectionCase" key={c.id} onClick={()=>onSelect(c.id)}><div><span>{c.organization_name}</span><h3>{c.title}</h3><p>{c.property_label||c.location_label||c.category}</p></div><div><span className={`status status-${c.status}`}>{statusLabels[c.status]}</span><small>{c.message_count} Nachrichten · {c.attachment_count} Belege</small></div></button>):<div className="emptyMini">Noch kein Mangel digital an eine Hausverwaltung übermittelt.</div>}</section></div>}

'''
    app=app.replace(component_anchor,comp+component_anchor,1)
app=app.replace("else if (view === 'search') content = <SearchArchiveView onSelect={setSelected} />;", "else if (view === 'search') content = <SearchArchiveView onSelect={setSelected} />;\n  else if (view === 'connections') content = <ConnectionsView onSelect={setSelected} />;")
# Show connections only for private accounts (management undefined/null organization).
needle="<button className={view === 'search' ? 'active' : ''} onClick={() => { setSelected(null); setView('search'); }}><span>S</span>Suche & Archiv</button>"
if needle in app and "setView('connections')" not in app:
    app=app.replace(needle,needle+"{!management?.organization&&<button className={view === 'connections' ? 'active' : ''} onClick={() => { setSelected(null); setView('connections'); }}><span>V</span>Verknüpfte Verwaltungen</button>}",1)
app_p.write_text(app)

css += r'''
/* v0.16 Beta-Härtung */
.connectionCards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}.connectionCards article{background:#fff;border:1px solid #dce2e5;border-radius:12px;padding:18px}.connectionCards article>span{font-size:10px;font-weight:800;letter-spacing:.09em;color:#68747d}.connectionCards h2{margin:6px 0}.connectionCards p{margin:0 0 4px}.connectionCards small{display:block;color:#77828a}.connectionCards b{display:block;margin-top:14px;font-size:12px;color:#2457d6}.connectionCase{width:100%;display:flex;justify-content:space-between;gap:20px;text-align:left;border:0;border-top:1px solid #e4e8ea;background:transparent;padding:14px 2px}.connectionCase:first-of-type{border-top:0}.connectionCase h3{margin:4px 0}.connectionCase p{margin:0;color:#68747d}.connectionCase>div:last-child{text-align:right}.connectionCase small{display:block;margin-top:7px;color:#7b858d}@media(max-width:800px){.connectionCards{grid-template-columns:1fr 1fr}}@media(max-width:560px){.connectionCards{grid-template-columns:1fr}.connectionCase{flex-direction:column}.connectionCase>div:last-child{text-align:left}}
'''
css_p.write_text(css)
print('v0.16 beta hardening prepared')
