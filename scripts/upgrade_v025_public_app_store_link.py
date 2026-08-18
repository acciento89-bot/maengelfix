from pathlib import Path

p = Path('client/src/App.jsx')
s = p.read_text()

app_store_url = 'https://apps.apple.com/de/app/maengelfix/id6801253878'

hero_old = """            <div className=\"heroActions\">\n              <button className=\"landingPrimary\" onClick={() => navigate(user ? '/app' : '/registrieren')}>{user ? 'MängelFix öffnen' : 'Kostenlos starten'} <span>→</span></button>\n              <button type=\"button\" className=\"landingSecondary\" onClick={() => document.getElementById('ablauf')?.scrollIntoView({ behavior: 'smooth' })}>So funktioniert's</button>\n            </div>"""
hero_new = f"""            <div className=\"heroActions\">\n              <button className=\"landingPrimary\" onClick={{() => navigate(user ? '/app' : '/registrieren')}}>{{user ? 'MängelFix öffnen' : 'Kostenlos starten'}} <span>→</span></button>\n              <a className=\"landingSecondary\" href=\"{app_store_url}\" target=\"_blank\" rel=\"noreferrer\" aria-label=\"MängelFix im Apple App Store laden\">Im App Store laden ↗</a>\n              <button type=\"button\" className=\"landingSecondary\" onClick={{() => document.getElementById('ablauf')?.scrollIntoView({{ behavior: 'smooth' }})}}>So funktioniert's</button>\n            </div>"""

if app_store_url not in s:
    if hero_old not in s:
        raise SystemExit('Hero action anchor not found')
    s = s.replace(hero_old, hero_new, 1)

p.write_text(s)
print('Public App Store download link added')
