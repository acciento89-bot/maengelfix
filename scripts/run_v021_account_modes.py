from pathlib import Path

upgrade_path = Path('scripts/upgrade_v021_account_modes.py')
source = upgrade_path.read_text()
start_marker = 'pattern = r"function Auth\\(\\{ mode, onSignedIn, navigate \\}\\) \\{.*?\\n\\}\\n\\nfunction SimpleAccountPage"'
end_marker = '# Dedicated registration URLs. /registrieren remains the neutral chooser.'
start = source.find(start_marker)
end = source.find(end_marker, start)
if start == -1 or end == -1:
    raise SystemExit('Could not patch Auth replacement logic in v0.21 upgrade')
replacement = '''auth_start = app.find("function Auth({ mode, onSignedIn, navigate }) {")
auth_end = app.find("function SimpleAccountPage", auth_start)
if auth_start == -1 or auth_end == -1:
    raise SystemExit('Auth component boundaries not found')
app = app[:auth_start] + new_auth + "\\n\\n" + app[auth_end:]

'''
source = source[:start] + replacement + source[end:]
exec(compile(source, str(upgrade_path), 'exec'), {'__name__': '__main__'})
