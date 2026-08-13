from pathlib import Path
p = Path('client/src/App.jsx')
s = p.read_text()
needle = "  useEffect(()=>{refreshWorkspaceState()},[view]);\n  const profileComplete = Boolean(user.street && user.postalCode && user.city);"
s = s.replace(needle, "  const profileComplete = Boolean(user.street && user.postalCode && user.city);", 1)
start = s.find('function Workspace({ user, setUser, onLogout, navigate }) {')
pos = s.find('  const profileComplete = Boolean(user.street && user.postalCode && user.city);', start)
if start < 0 or pos < 0:
    raise SystemExit('workspace marker missing')
effect = "  useEffect(()=>{refreshWorkspaceState()},[view]);\n"
if effect not in s[start:pos]:
    s = s[:pos] + effect + s[pos:]
p.write_text(s)
