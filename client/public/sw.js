const CACHE='maengelfix-static-v1';
const STATIC=['/maengelfix-mark.svg','/manifest.webmanifest'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(c=>c.addAll(STATIC)));self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));self.clients.claim();});
self.addEventListener('fetch',event=>{
  const req=event.request;
  if(req.method!=='GET') return;
  const url=new URL(req.url);
  if(url.origin!==self.location.origin) return;
  if(req.mode==='navigate' || url.pathname.startsWith('/api/')) return;
  event.respondWith(caches.match(req).then(hit=>hit||fetch(req).then(res=>{if(res.ok && ['script','style','image','font'].includes(req.destination)){const copy=res.clone();caches.open(CACHE).then(c=>c.put(req,copy));}return res;})));
});
