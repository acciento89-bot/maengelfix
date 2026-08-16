from pathlib import Path

app_p = Path('client/src/App.jsx')
css_p = Path('client/src/maengelfix-pro.css')
app = app_p.read_text()
css = css_p.read_text()

# 1) Make account deletion easy to find for App Review.
old = "function ProfileView({ user, onSaved }) {"
new = "function ProfileView({ user, onSaved, onOpenAccount }) {"
if new not in app:
    if old not in app:
        raise SystemExit('ProfileView signature anchor not found')
    app = app.replace(old, new, 1)

old = '<div className="workspacePage"><div className="workspaceHeading"><div><span>PROFIL</span><h1>Absender & Konto</h1><p>Diese Angaben erscheinen als Absender in deiner MängelFix-PDF.</p></div></div><div className="profileLayout">'
new = '<div className="workspacePage"><div className="workspaceHeading"><div><span>PROFIL</span><h1>Absender & Konto</h1><p>Diese Angaben erscheinen als Absender in deiner MängelFix-PDF.</p></div><button type="button" className="secondaryButton" onClick={onOpenAccount}>Konto & Datenschutz</button></div><div className="profileLayout">'
if 'onClick={onOpenAccount}>Konto & Datenschutz</button>' not in app:
    if old not in app:
        raise SystemExit('Profile heading anchor not found')
    app = app.replace(old, new, 1)

old = "else content = <ProfileView user={user} onSaved={setUser} />;"
new = "else content = <ProfileView user={user} onSaved={setUser} onOpenAccount={()=>{setSelected(null);setView('security')}} />;"
if new not in app:
    if old not in app:
        raise SystemExit('ProfileView wiring anchor not found')
    app = app.replace(old, new, 1)

old = "<button className={view === 'profile' ? 'active' : ''} onClick={goProfile}><span>P</span>Profil {!profileComplete && <i />}</button><button onClick={()=>setShowOnboarding(true)}><span>?</span>Einführung</button>"
new = "<button className={view === 'profile' ? 'active' : ''} onClick={goProfile}><span>P</span>Profil {!profileComplete && <i />}</button><button className={view === 'security' ? 'active' : ''} onClick={()=>{setSelected(null);setView('security')}}><span>⚙</span>Konto & Datenschutz</button><button onClick={()=>setShowOnboarding(true)}><span>?</span>Einführung</button>"
if "setView('security')}}><span>⚙</span>Konto & Datenschutz" not in app:
    if old not in app:
        raise SystemExit('Sidebar account navigation anchor not found')
    app = app.replace(old, new, 1)

old = '<p>Persönliche Daten und private Vorgänge werden gelöscht. Bist du noch Inhaber einer Verwaltung, wird die Löschung blockiert.</p>'
new = '<p>Dein MängelFix-Konto, deine persönlichen Daten und deine privaten Vorgänge werden dauerhaft gelöscht. Dieser Vorgang kann nicht rückgängig gemacht werden. Bist du noch Inhaber einer Verwaltung, wird die Löschung blockiert, bis die Inhaberschaft übertragen wurde.</p><p className="accountDeleteNotice"><b>Wichtig bei Apple-Abonnements:</b> Das Löschen deines MängelFix-Kontos beendet ein über den App Store abgeschlossenes Abonnement nicht automatisch. Verwalte oder kündige dein Apple-Abonnement separat in deiner Apple-Abonnementverwaltung.</p><div className="accountDeleteLegal"><a href="/datenschutz" target="_blank" rel="noreferrer">Datenschutz</a><a href="/nutzungsbedingungen" target="_blank" rel="noreferrer">Nutzungsbedingungen (EULA)</a></div>'
if 'Wichtig bei Apple-Abonnements:' not in app:
    if old not in app:
        raise SystemExit('Account deletion description anchor not found')
    app = app.replace(old, new, 1)

# 2) Make the subscription value, duration and terms unmistakable.
old = "Free dauerhaft nutzen oder für 4,99 € auf Privat Pro erweitern."
new = "Privat Pro schaltet unbegrenzte Vorgänge, erweiterte Belege, Fristen, Aufgaben, Kalender, Archiv, Auswertungen und Übergabe-/Abnahmeprotokolle frei."
if new not in app:
    if old not in app:
        raise SystemExit('Billing intro anchor not found')
    app = app.replace(old, new, 1)

old = "<><li>Unbegrenzte aktive Vorgänge</li><li>Erweiterte Fotos, PDFs & Belege</li><li>Fristen, Aufgaben & Kalender</li><li>Archiv, Analysen & Übergabeprotokolle</li></>"
new = "<><li>Unbegrenzt aktive Mängelvorgänge statt maximal 5 in Free</li><li>Mehr als 3 Fotos sowie PDF-Dokumente und weitere Belege je Vorgang</li><li>Fristen, Aufgaben, Erinnerungen und Kalender</li><li>Suche & Archiv sowie persönliche Auswertungen</li><li>Übergabe- und Abnahmeprotokolle</li></>"
if 'Unbegrenzt aktive Mängelvorgänge statt maximal 5 in Free' not in app:
    if old not in app:
        raise SystemExit('Private Pro benefits anchor not found')
    app = app.replace(old, new, 1)

anchor = '</ul>{free?<button className="secondaryButton" disabled>Im Konto enthalten</button>'
disclosure = '''</ul>{!free&&<div className="subscriptionDisclosure"><div className="subscriptionDisclosureHead"><b>{cycle==='yearly'?'Abonnement · 1 Jahr':'Abonnement · 1 Monat'}</b><span>{price(plan).toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2})} € {cycle==='yearly'?'/ Jahr':'/ Monat'}</span></div>{cycle==='yearly'&&<p><b>Preis je Monat:</b> {(price(plan)/12).toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2})} € bei jährlicher Abrechnung.</p>}<p>Mit dem Abschluss erhältst du für die gewählte Laufzeit die oben aufgeführten Funktionen dieses Tarifs. Das Abonnement verlängert sich automatisch um die gewählte Laufzeit, bis es über die jeweilige Abonnementverwaltung gekündigt wird.</p><div className="subscriptionLegalLinks"><a href="/datenschutz" target="_blank" rel="noreferrer">Datenschutz</a><a href="/nutzungsbedingungen" target="_blank" rel="noreferrer">Nutzungsbedingungen (EULA)</a></div></div>}{free?<button className="secondaryButton" disabled>Im Konto enthalten</button>'''
if 'className="subscriptionDisclosure"' not in app:
    if anchor not in app:
        raise SystemExit('Subscription disclosure anchor not found')
    app = app.replace(anchor, disclosure, 1)

app_p.write_text(app)

if '/* v0.25 App Review fixes */' not in css:
    css += '''\n/* v0.25 App Review fixes */\n.subscriptionDisclosure{margin:14px 0 16px;padding:14px;border:1px solid #d8dee4;border-radius:10px;background:#f8fafb;font-size:13px;line-height:1.5}.subscriptionDisclosureHead{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:8px}.subscriptionDisclosureHead b{font-size:13px}.subscriptionDisclosureHead span{font-weight:800;text-align:right}.subscriptionDisclosure p{margin:7px 0;color:#53606b}.subscriptionLegalLinks,.accountDeleteLegal{display:flex;gap:14px;flex-wrap:wrap;margin-top:10px}.subscriptionLegalLinks a,.accountDeleteLegal a{text-decoration:underline;font-weight:700}.accountDeleteNotice{margin-top:12px;padding:12px 14px;border-radius:9px;background:#fff7ed;border:1px solid #fed7aa;line-height:1.5}@media(max-width:760px){.subscriptionDisclosureHead{flex-direction:column}.subscriptionDisclosureHead span{text-align:left}}\n'''
    css_p.write_text(css)

print('v0.25 App Review fixes prepared')
