from pathlib import Path

p = Path('client/src/App.jsx')
s = p.read_text()

old = '''              <a className="landingSecondary" href="https://apps.apple.com/de/app/m%C3%A4ngelfix/id6759452843?l=de" target="_blank" rel="noreferrer" aria-label="MängelFix im Apple App Store laden">Im App Store laden ↗</a>'''
new = '''              <a
                href="https://apps.apple.com/de/app/m%C3%A4ngelfix/id6759452843?l=de"
                target="_blank"
                rel="noreferrer"
                aria-label="MängelFix im App Store laden"
                style={{ display: 'inline-block', lineHeight: 0 }}
              >
                <img
                  src="https://tools.applemediaservices.com/api/badges/download-on-the-app-store/black/de-de?size=250x83"
                  alt="Laden im App Store"
                  width="170"
                  height="56"
                  style={{ display: 'block', width: '170px', height: 'auto' }}
                />
              </a>'''

if old not in s:
    raise SystemExit('Current MängelFix text App Store button not found')

s = s.replace(old, new, 1)
p.write_text(s)
print('MängelFix now uses the official Apple App Store badge')
