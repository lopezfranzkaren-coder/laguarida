// Presupuesto rápido · guarda la pantalla en el celular para que abra al instante,
// aunque el servidor de Render esté "dormido". Los precios se actualizan aparte.
const CACHE = 'lg-movil-v1';

self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c => c.add('/movil')).catch(() => {}));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;

  // La pantalla: se muestra la copia guardada y se actualiza por detrás
  if (url.origin === location.origin && url.pathname === '/movil') {
    e.respondWith(caches.open(CACHE).then(async c => {
      const guardada = await c.match('/movil');
      const red = fetch(e.request).then(r => {
        if (r.ok && !r.redirected) c.put('/movil', r.clone());
        return r;
      }).catch(() => guardada);
      return guardada || red;
    }));
    return;
  }

  // Ícono y tipografías: se guardan la primera vez
  if (url.pathname === '/movil-icono.png' || url.host.includes('fonts.g')) {
    e.respondWith(caches.open(CACHE).then(async c => {
      const g = await c.match(e.request);
      if (g) return g;
      const r = await fetch(e.request);
      if (r.ok || r.type === 'opaque') c.put(e.request, r.clone());
      return r;
    }));
  }
});
