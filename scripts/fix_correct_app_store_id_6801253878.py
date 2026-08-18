from pathlib import Path

OLD_URL = 'https://apps.apple.com/de/app/m%C3%A4ngelfix/id6759452843?l=de'
NEW_URL = 'https://apps.apple.com/de/app/maengelfix/id6801253878'
OLD_ID = '6759452843'

paths = [
    Path('client/src/App.jsx'),
    Path('scripts/upgrade_v025_public_app_store_link.py'),
    Path('scripts/upgrade_v026_official_apple_badge.py'),
]

changed = []
for path in paths:
    text = path.read_text()
    updated = text.replace(OLD_URL, NEW_URL).replace(OLD_ID, '6801253878')
    if updated != text:
        path.write_text(updated)
        changed.append(str(path))

if not changed:
    raise SystemExit('No old MängelFix App Store ID found')

print('Corrected MängelFix App Store URL in: ' + ', '.join(changed))
