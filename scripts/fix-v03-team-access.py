from pathlib import Path

p = Path('server/index.js')
s = p.read_text()
old = """app.post('/api/cases/:caseId/attachments', auth, upload.array('images', 5), async (req, res, next) => {\n  try {\n    const owner = await pool.query('SELECT 1 FROM defect_cases WHERE id=$1 AND user_id=$2', [req.params.caseId, req.user.id]);\n    if (!owner.rowCount) return res.status(404).json({ error: 'Mangel nicht gefunden.' });"""
new = """app.post('/api/cases/:caseId/attachments', auth, upload.array('images', 5), async (req, res, next) => {\n  try {\n    const accessible = await canAccessCase(req.user.id, req.params.caseId);\n    if (!accessible) return res.status(404).json({ error: 'Mangel nicht gefunden.' });"""
if old in s:
    s = s.replace(old, new, 1)
    p.write_text(s)
elif new not in s:
    raise SystemExit('Attachment access marker not found')
print('Team attachment access OK')
