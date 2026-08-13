from pathlib import Path
p=Path('server/index.js')
s=p.read_text()
old="""app.use(express.static(publicDir, { index: false, maxAge: production ? '1h' : 0 }));
app.use((req, res, next) => {
  if (req.method !== 'GET' || req.path.startsWith('/api/')) return next();
  res.sendFile(path.join(publicDir, 'index.html'));
});
"""
new="""app.use(express.static(publicDir, {
  index: false,
  maxAge: production ? '1h' : 0,
  setHeaders: (res, filePath) => {
    if (filePath.endsWith('.html')) {
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.setHeader('Content-Disposition', 'inline');
    }
  }
}));
app.use((req, res, next) => {
  if (req.method !== 'GET' || req.path.startsWith('/api/')) return next();
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.setHeader('Content-Disposition', 'inline');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.sendFile(path.join(publicDir, 'index.html'));
});
"""
if old not in s:
    raise SystemExit('SPA fallback block not found')
p.write_text(s.replace(old,new,1))
print('iOS inline HTML headers fixed')
