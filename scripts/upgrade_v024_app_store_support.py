from pathlib import Path

p = Path('client/src/App.jsx')
s = p.read_text()

footer_old = """      <div className=\"footerLinks\">\n        <button onClick={() => navigate('/impressum')}>Impressum</button>\n        <button onClick={() => navigate('/datenschutz')}>Datenschutz</button>\n        <button onClick={() => navigate('/nutzungsbedingungen')}>Nutzungsbedingungen</button>\n      </div>"""
footer_new = """      <div className=\"footerLinks\">\n        <button onClick={() => navigate('/support')}>Support</button>\n        <button onClick={() => navigate('/impressum')}>Impressum</button>\n        <button onClick={() => navigate('/datenschutz')}>Datenschutz</button>\n        <button onClick={() => navigate('/nutzungsbedingungen')}>Nutzungsbedingungen</button>\n      </div>"""
if "navigate('/support')" not in s:
    if footer_old not in s:
        raise SystemExit('Footer anchor not found')
    s = s.replace(footer_old, footer_new, 1)

content_anchor = """  const content = {\n    impressum: {"""
support_content = """  const content = {\n    support: {\n      eyebrow: 'MÄNGELFIX SUPPORT',\n      title: 'Hilfe & Kontakt',\n      sections: [\n        ['Support für MängelFix', <><p>Du hast eine Frage zur App, zu deinem Konto, zu einem Kauf oder eine Idee für eine Verbesserung? Schreib uns – wir helfen dir gerne weiter.</p><p><b>E-Mail:</b> <a href=\"mailto:contact@kamilunavo.com\">contact@kamilunavo.com</a></p></>],\n        ['Anbieter & Kontakt', <p><b>Kamilunavo</b><br />Inhaber: Piotr Kaminski<br />Otto-Braun-Straße 14<br />40595 Düsseldorf<br />Deutschland</p>],\n        ['Käufe & Abonnements', <p>Abonnements, die in der iPhone- oder iPad-App abgeschlossen wurden, werden über den Apple App Store verwaltet. In MängelFix kannst du Käufe wiederherstellen; Änderungen oder Kündigungen erfolgen über deine Apple-Abonnementverwaltung.</p>],\n        ['Konto & Datenschutz', <p>Passwort, E-Mail-Adresse, Datenexport und die dauerhafte Kontolöschung findest du nach der Anmeldung unter Konto & Datenschutz. Weitere Informationen stehen in unserer Datenschutzerklärung.</p>],\n        ['Bei einer Support-Anfrage hilfreich', <p>Nenne uns bitte die verwendete Plattform (iPhone oder iPad), deine MängelFix-App-Version und eine kurze Beschreibung des Problems. Sende keine Passwörter, Apple-Schlüssel oder andere Zugangsdaten per E-Mail.</p>]\n      ]\n    },\n    impressum: {"""
if "eyebrow: 'MÄNGELFIX SUPPORT'" not in s:
    if content_anchor not in s:
        raise SystemExit('Legal content anchor not found')
    s = s.replace(content_anchor, support_content, 1)

route_anchor = """  if (state.loading) return <div className=\"brandSplash\"><Logo /><div className=\"loader\" /></div>;\n  if (path === '/impressum') return <LegalPage type=\"impressum\" navigate={navigate} />;"""
route_new = """  if (state.loading) return <div className=\"brandSplash\"><Logo /><div className=\"loader\" /></div>;\n  if (path === '/support') return <LegalPage type=\"support\" navigate={navigate} />;\n  if (path === '/impressum') return <LegalPage type=\"impressum\" navigate={navigate} />;"""
if "path === '/support'" not in s:
    if route_anchor not in s:
        raise SystemExit('Route anchor not found')
    s = s.replace(route_anchor, route_new, 1)

p.write_text(s)
print('App Store support page prepared')
