from pathlib import Path
p=Path('server/index.js')
s=p.read_text()
old="""app.use(express.static(publicDir, { index: false, maxAge: production ? '1h' : 0 }));
app.use((req, res, next) => {
  if (req.method !== 'GET' || req.path.startsWith('/api/')) return next();
  res.sendFile(path.join(publicDir, 'index.html'));
});
"""
new="""const indexHtml = fs.readFileSync(path.join(publicDir, 'index.html'), 'utf8');

app.use(express.static(publicDir, { index: false, maxAge: production ? '1h' : 0 }));
app.use((req, res, next) => {
  if (req.method !== 'GET' || req.path.startsWith('/api/')) return next();
  res.status(200)
    .set({
      'Content-Type': 'text/html; charset=utf-8',
      'Content-Disposition': 'inline',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff'
    })
    .send(indexHtml);
});
"""
if old not in s:
    raise SystemExit('SPA fallback block not found; refusing blind edit')
p.write_text(s.replace(old,new,1))
print('Root/SPA HTML is now sent as HTML text, not via sendFile')
