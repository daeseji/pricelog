/* 싸다구 서비스 워커
 * - 알림을 누르면 싸다구를 열어요
 * - 앱으로 설치하면 브라우저가 정한 때(보통 하루 한두 번) 창이 닫혀 있어도 가격을 확인해 알려요
 * 쿠팡 API는 부르지 않고, 매일 아침 저장소에 쌓인 가격 기록(JSON)만 읽어요.
 */
importScripts('assets/alerts.js?v=dfd8490f');

const STATE_CACHE = 'sdg-state-v1';
const STATE_URL = new URL('__sdg_state', self.registration.scope).href;
const DEFAULT_DATA = 'https://raw.githubusercontent.com/daeseji/pricelog/main/data';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

async function readState() {
  const c = await caches.open(STATE_CACHE);
  const r = await c.match(STATE_URL);
  return r ? r.json() : { watch: {}, sent: {} };
}

async function writeState(s) {
  const c = await caches.open(STATE_CACHE);
  await c.put(STATE_URL, new Response(JSON.stringify(s), { headers: { 'content-type': 'application/json' } }));
}

async function check() {
  const state = await readState();
  const names = Object.keys(state.watch || {}).filter(n => SDGAlerts.hasActive(state.watch[n].rule));
  if (!names.length) return;
  const base = state.dataBase || DEFAULT_DATA;
  const res = await fetch(base + '/prices.json?_=' + Date.now(), { cache: 'no-store' });
  if (!res.ok) return;
  const { history = {} } = await res.json();
  state.sent = state.sent || {};
  for (const name of names) {
    const h = history[name] || [];
    if (!h.length) continue;
    const sent = state.sent[name] || {};
    const list = SDGAlerts.fresh(h, state.watch[name].rule, sent);
    if (!list.length) continue;
    const last = h[h.length - 1];
    await self.registration.showNotification(`${name} ${SDGAlerts.won(last.price)}`, {
      body: list.map(x => x.text).join(' · '),
      icon: 'icon-192.png',
      badge: 'favicon-32.png',
      tag: 'sdg-' + name,
      data: { url: new URL('./#' + encodeURIComponent(name), self.registration.scope).href },
    });
    state.sent[name] = SDGAlerts.mark(sent, list, last);
  }
  await writeState(state);
}

self.addEventListener('periodicsync', e => {
  if (e.tag === 'sdg-price') e.waitUntil(check());
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || self.registration.scope;
  e.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const w of wins) {
      if (w.url.startsWith(self.registration.scope) && 'focus' in w) {
        await w.focus();
        if ('navigate' in w) return w.navigate(url);
        return;
      }
    }
    return self.clients.openWindow(url);
  })());
});
