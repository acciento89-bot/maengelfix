from pathlib import Path

root = Path('.')
server_path = root / 'server/index.js'
app_path = root / 'client/src/App.jsx'

server = server_path.read_text()
app = app_path.read_text()

old = "res.setHeader('Content-Type', 'application/pdf');\n    res.setHeader('Content-Disposition', `attachment; filename=\"maengelfix-${item.id}.pdf\"`);"
new = "res.setHeader('Content-Type', 'application/pdf');\n    const forceDownload = String(req.query.download || '') === '1';\n    res.setHeader('Content-Disposition', `${forceDownload ? 'attachment' : 'inline'}; filename=\"maengelfix-${item.id}.pdf\"`);"
if old not in server:
    raise SystemExit('PDF response header pattern not found')
server = server.replace(old, new, 1)

# Avoid full-document navigations for public section links on mobile Safari.
app = app.replace('<a href="/#ablauf">So funktioniert\'s</a>', '<button type="button" onClick={() => { navigate(\'/\'); requestAnimationFrame(() => document.getElementById(\'ablauf\')?.scrollIntoView({ behavior: \'smooth\' })); }}>So funktioniert\'s</button>')
app = app.replace('<a href="/#funktionen">Funktionen</a>', '<button type="button" onClick={() => { navigate(\'/\'); requestAnimationFrame(() => document.getElementById(\'funktionen\')?.scrollIntoView({ behavior: \'smooth\' })); }}>Funktionen</button>')
app = app.replace('<a href="/#tarife">Tarife</a>', '<button type="button" onClick={() => { navigate(\'/\'); requestAnimationFrame(() => document.getElementById(\'tarife\')?.scrollIntoView({ behavior: \'smooth\' })); }}>Tarife</button>')
app = app.replace('<a className="landingSecondary" href="#ablauf">So funktioniert\'s</a>', '<button type="button" className="landingSecondary" onClick={() => document.getElementById(\'ablauf\')?.scrollIntoView({ behavior: \'smooth\' })}>So funktioniert\'s</button>')

# Opening is now explicitly inline; downloading is an explicit second action.
old_pdf = '<a className="primaryButton linkButton" href={`/api/cases/${item.id}/pdf`} target="_blank" rel="noreferrer">PDF erstellen</a>'
new_pdf = '<a className="primaryButton linkButton" href={`/api/cases/${item.id}/pdf`} target="_blank" rel="noreferrer">PDF öffnen</a><a className="secondaryButton linkButton" href={`/api/cases/${item.id}/pdf?download=1`}>PDF herunterladen</a>'
if old_pdf not in app:
    raise SystemExit('PDF client link pattern not found')
app = app.replace(old_pdf, new_pdf, 1)

server_path.write_text(server)
app_path.write_text(app)
print('Focused iOS download behavior fix applied')
