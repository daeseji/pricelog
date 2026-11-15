// 싸다구 '내 상품': 방문자가 직접 담은 쿠팡 상품과 가격 기록 (이 기기의 브라우저에만 저장돼요)
(() => {
  // 제휴 링크 서버 주소 (worker/README.md 참고). 비어 있으면 쿠팡 상품 페이지로 바로 연결해요.
  const LINK_API = '';

  const KEY = 'sadagu:mine:v1';
  const ROOT = '../';
  const DATA = location.hostname.endsWith('.github.io') ? 'https://raw.githubusercontent.com/daeseji/pricelog/main/data' : ROOT + 'data';
  const HOSTS = ['www.coupang.com', 'coupang.com', 'm.coupang.com'];
  const SHORT = ['coupa.ng', 'link.coupang.com'];
  const LINK_RE = /^https:\/\/(link\.coupang\.com|coupa\.ng)\/[A-Za-z0-9/_?=&.-]+$/;

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const won = (n) => Math.round(n).toLocaleString('ko-KR') + '원';
  const today = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const b64 = (s) => btoa(unescape(encodeURIComponent(s))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const go = (url) => `${ROOT}go.html?u=${b64(url)}`;
  const toNum = (v) => {
    const n = Math.round(Number(String(v ?? '').replace(/[^\d.]/g, '')));
    return Number.isFinite(n) && n > 0 && n < 1e9 ? n : 0;
  };

  /* ---------- 주소 정리 ----------
     상품 페이지 주소만 받아요. 줄인 주소(coupa.ng, link.coupang.com/a/...)는 열어 봐야 원래 상품을 알 수 있는데,
     그렇게 대신 열면 그 링크의 클릭으로 잡힐 수 있어서 읽지 않아요. */
  function parse(raw) {
    let u;
    try {
      u = new URL(String(raw || '').trim());
    } catch {
      return null;
    }
    if (u.protocol !== 'https:' && u.protocol !== 'http:') return null;
    let id = '';
    if (HOSTS.includes(u.hostname)) {
      id = (u.pathname.match(/^\/(?:vp|vm)\/products\/(\d{3,15})/) || [])[1] || '';
    } else if (u.hostname === 'link.coupang.com' && u.pathname.startsWith('/re/')) {
      // 주소 안에 상품 번호(pageKey)가 그대로 적힌 긴 링크는 열지 않고도 읽을 수 있어요
      const k = u.searchParams.get('pageKey') || '';
      id = /^\d{3,15}$/.test(k) ? k : '';
    } else if (SHORT.includes(u.hostname)) {
      return { short: true };
    }
    if (!id) return null;
    const digits = (v) => (/^\d{1,15}$/.test(v || '') ? v : '');
    const itemId = digits(u.searchParams.get('itemId'));
    const vendorItemId = digits(u.searchParams.get('vendorItemId'));
    const q = new URLSearchParams();
    if (itemId) q.set('itemId', itemId);
    if (vendorItemId) q.set('vendorItemId', vendorItemId);
    const qs = q.toString();
    return { productId: id, itemId, url: `https://www.coupang.com/vp/products/${id}${qs ? '?' + qs : ''}` };
  }

  /* ---------- 저장 ---------- */
  function clean(x) {
    if (!x || typeof x !== 'object') return null;
    const p = parse(x.url);
    const name = String(x.name || '').trim().slice(0, 60);
    if (!p || p.short || !name) return null;
    const prices = (Array.isArray(x.prices) ? x.prices : [])
      .map((r) => ({ d: /^\d{4}-\d{2}-\d{2}$/.test(r && r.d) ? r.d : '', p: toNum(r && r.p) }))
      .filter((r) => r.d && r.p)
      .slice(-180);
    return {
      id: /^[a-z0-9]{4,20}$/.test(x.id || '') ? x.id : Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
      url: p.url,
      name,
      added: /^\d{4}-\d{2}-\d{2}$/.test(x.added || '') ? x.added : today(),
      target: toNum(x.target) || null,
      prices,
      link: LINK_RE.test(x.link || '') ? x.link : '',
    };
  }
  function load() {
    try {
      const d = JSON.parse(localStorage.getItem(KEY) || 'null');
      return { items: d && Array.isArray(d.items) ? d.items.map(clean).filter(Boolean) : [] };
    } catch {
      return { items: [] };
    }
  }
  let state = load();
  function save() {
    try {
      localStorage.setItem(KEY, JSON.stringify({ app: 'sadagu-mine', v: 1, items: state.items }));
      return true;
    } catch {
      toast('브라우저에 저장하지 못했어요. 사생활 보호 모드인지 확인해 주세요.');
      return false;
    }
  }

  /* ---------- 싸다구가 매일 기록하는 상품과 맞춰 보기 ---------- */
  let catalog = [];
  let history = {};
  async function loadCatalog() {
    try {
      const bust = '?_=' + Math.floor(Date.now() / 600000);
      const [p, h] = await Promise.all([
        fetch(DATA + '/products.json' + bust).then((r) => r.json()),
        fetch(DATA + '/prices.json' + bust).then((r) => r.json()),
      ]);
      history = (h && h.history) || {};
      catalog = ((p && p.products) || [])
        .map((x) => {
          const q = parse(x.url);
          return q && !q.short ? { name: x.name, productId: q.productId, itemId: String(x.item_id || q.itemId || ''), link_b64: x.link_b64 || '' } : null;
        })
        .filter(Boolean);
    } catch {
      catalog = [];
    }
    render();
  }
  // 옵션 번호까지 같아야 같은 상품으로 봐요 (다른 용량·수량의 가격이 섞이지 않게)
  function tracked(item) {
    const p = parse(item.url);
    if (!p || p.short) return null;
    return catalog.find((c) => c.productId === p.productId && (c.itemId ? c.itemId === p.itemId : true)) || null;
  }

  /* ---------- 제휴 링크 ---------- */
  async function requestLink(url) {
    if (!LINK_API) return '';
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 9000);
    try {
      // 본문을 일반 텍스트로 보내서 브라우저의 사전 확인 요청 없이 한 번에 보내요
      const r = await fetch(LINK_API, { method: 'POST', body: JSON.stringify({ url }), signal: ctrl.signal });
      const d = await r.json().catch(() => null);
      return d && LINK_RE.test(d.link || '') ? d.link : '';
    } catch {
      return '';
    } finally {
      clearTimeout(timer);
    }
  }

  async function ensureLink(item) {
    if (item.link || !LINK_API || tracked(item)) return;
    const link = await requestLink(item.url);
    if (link) {
      item.link = link;
      save();
    }
  }

  // '제휴 링크 끄기'를 켠 브라우저에서는 일반 쿠팡 상품 주소로 열어요 (assets/noaff.js)
  const noAff = () => !!(window.SDG_NOAFF && window.SDG_NOAFF());

  function buyHref(item) {
    if (noAff()) return item.url;
    const t = tracked(item);
    if (t && t.link_b64) return `${ROOT}go.html?u=${t.link_b64}`;
    if (item.link) return go(item.link);
    return go(item.url);
  }
  const needsLink = (item) => !!LINK_API && !noAff() && !item.link && !tracked(item);

  /* ---------- 화면 ---------- */
  function seriesOf(item) {
    const t = tracked(item);
    const auto = t ? (history[t.name] || []).map((x) => ({ d: String(x.date).slice(0, 10), p: Number(x.price) })).filter((x) => x.p > 0) : [];
    return auto.length ? { auto: true, list: auto } : { auto: false, list: item.prices || [] };
  }

  function spark(list) {
    if (list.length < 2) return '';
    const ps = list.slice(-30).map((x) => x.p);
    const min = Math.min(...ps);
    const max = Math.max(...ps);
    const w = 140;
    const h = 44;
    const pts = ps.map((p, i) => `${((i / (ps.length - 1)) * (w - 4) + 2).toFixed(1)},${(max === min ? h / 2 : h - 4 - ((p - min) / (max - min)) * (h - 8)).toFixed(1)}`);
    return `<svg class="mine-spark" viewBox="0 0 ${w} ${h}" aria-hidden="true"><polyline points="${pts.join(' ')}" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
  }

  function card(item) {
    const { auto, list } = seriesOf(item);
    const last = list.length ? list[list.length - 1].p : null;
    const min = list.length ? Math.min(...list.map((x) => x.p)) : null;
    const max = list.length ? Math.max(...list.map((x) => x.p)) : null;
    let badge = '';
    if (last != null && item.target && last <= item.target) badge = '<span class="badge deal">목표가 도달</span>';
    else if (last != null && list.length >= 3 && last === min && max > min) badge = '<span class="badge good">기록 중 최저</span>';
    else if (auto) badge = '<span class="badge mute">매일 기록</span>';
    const meta = auto
      ? `싸다구가 매일 아침 기록해요 · ${list.length}번 기록`
      : tracked(item)
        ? `싸다구가 곧 매일 기록을 시작해요 · 직접 기록 ${list.length}번`
        : `직접 기록 ${list.length}번 · ${esc(item.added)}에 담음`;
    const price =
      last == null
        ? '<b class="none">아직 기록이 없어요</b><span>살 때 본 가격을 적어 보세요</span>'
        : `<b class="num">${won(last)}</b><span class="num">최저 ${won(min)}${item.target ? ` · 목표 ${won(item.target)}` : ''}</span>`;
    const id = esc(item.id);
    // 쿠팡 버튼은 다른 버튼과 떨어진 맨 아래 줄에 혼자 두어요 (잘못 누르는 일이 없게)
    const label = noAff() ? '쿠팡에서 보기 (일반 주소)' : '쿠팡에서 보기';
    const buy = needsLink(item)
      ? `<button class="btn" type="button" data-buy="${id}">${label}</button>`
      : `<a class="btn" href="${esc(buyHref(item))}" target="_blank" rel="${noAff() ? 'noopener' : 'sponsored nofollow noopener'}">${label}</a>`;
    const log = auto
      ? ''
      : `<form class="mine-log" data-log="${id}"><label class="sr" for="log-${id}">${esc(item.name)} 오늘 본 가격</label><input id="log-${id}" type="text" inputmode="numeric" autocomplete="off" placeholder="오늘 본 가격(원)"><button class="btn ghost" type="submit">기록</button></form>`;
    return `<article class="mine-item" data-id="${id}">
      <div class="mine-top"><div><h3>${esc(item.name)}</h3><p class="mine-meta">${meta}</p>
        <div class="mine-manage"><button class="mine-txt" type="button" data-target="${id}">목표가 정하기</button><button class="mine-txt" type="button" data-del="${id}">목록에서 빼기</button></div></div>${badge}</div>
      <div class="mine-body"><div class="mine-price">${price}</div>${spark(list)}</div>
      ${log}
      <div class="mine-cta">${buy}</div>
    </article>`;
  }

  function render() {
    const items = state.items;
    $('m-list').innerHTML = items.map(card).join('');
    $('m-empty').hidden = items.length > 0;
    $('m-count').textContent = `${items.length}개`;
  }

  let toastTimer;
  function toast(msg) {
    const t = $('toast');
    t.textContent = msg;
    t.classList.add('on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('on'), 2400);
  }

  function showError(msg) {
    const e = $('m-error');
    e.textContent = msg;
    e.hidden = !msg;
  }

  /* ---------- 담기 ---------- */
  $('mine-form').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const p = parse($('m-url').value);
    const name = $('m-name').value.trim();
    if (!p) return showError('쿠팡 상품 페이지 주소를 넣어 주세요. 주소에 coupang.com/vp/products/ 가 들어 있으면 돼요.');
    if (p.short) return showError('줄인 주소(공유 링크)는 읽을 수 없어요. 링크를 한 번 열어 쿠팡 상품 페이지가 뜨면, 주소창의 주소를 복사해 붙여 넣어 주세요.');
    if (!name) return showError('목록에서 알아보기 쉬운 상품 이름을 적어 주세요.');
    if (state.items.some((x) => x.url === p.url)) return showError('이미 목록에 있는 상품이에요.');
    if (state.items.length >= 200) return showError('상품은 200개까지 담을 수 있어요. 안 쓰는 상품을 지운 뒤 다시 담아 주세요.');
    showError('');
    const price = toNum($('m-price').value);
    const item = clean({
      url: p.url,
      name,
      added: today(),
      target: toNum($('m-target').value),
      prices: price ? [{ d: today(), p: price }] : [],
    });
    state.items.unshift(item);
    if (!save()) return;
    ev.target.reset();
    render();
    toast(tracked(item) ? '담았어요. 싸다구가 매일 기록하는 상품이에요' : '목록에 담았어요');
  });

  /* ---------- 가격 기록 ---------- */
  $('m-list').addEventListener('submit', (ev) => {
    const form = ev.target.closest('[data-log]');
    if (!form) return;
    ev.preventDefault();
    const item = state.items.find((x) => x.id === form.dataset.log);
    const value = toNum(form.querySelector('input').value);
    if (!item || !value) return toast('가격을 숫자로 적어 주세요');
    const d = today();
    item.prices = (item.prices || []).filter((x) => x.d !== d).concat({ d, p: value }).slice(-180);
    save();
    render();
    toast('오늘 가격을 기록했어요');
  });

  /* ---------- 목표가, 삭제, 쿠팡에서 보기 ---------- */
  $('m-list').addEventListener('click', async (ev) => {
    const tgt = ev.target.closest('[data-target]');
    if (tgt) {
      const item = state.items.find((x) => x.id === tgt.dataset.target);
      if (!item) return;
      const v = prompt(`'${item.name}' 목표 가격을 적어 주세요. 비우면 목표가를 지워요.`, item.target || '');
      if (v === null) return;
      item.target = toNum(v) || null;
      save();
      render();
      return toast(item.target ? `목표가를 ${won(item.target)}으로 정했어요` : '목표가를 지웠어요');
    }
    const del = ev.target.closest('[data-del]');
    if (del) {
      const item = state.items.find((x) => x.id === del.dataset.del);
      if (item && confirm(`'${item.name}'을(를) 목록에서 지울까요? 적어 둔 가격도 함께 지워져요.`)) {
        state.items = state.items.filter((x) => x !== item);
        save();
        render();
      }
      return;
    }
    const btn = ev.target.closest('button[data-buy]');
    if (!btn) return; // 링크가 준비된 버튼은 평범한 링크라 그대로 열려요
    const item = state.items.find((x) => x.id === btn.dataset.buy);
    if (!item) return;
    // 링크는 누른 순간에만 만들어요. 새 탭에 '이동 중' 화면을 먼저 띄우고, 링크가 준비되면 그 탭에서 쿠팡을 열어요.
    // 링크를 못 만들면 수수료 없는 일반 상품 페이지로 열어요.
    const win = window.open(ROOT + 'go.html?wait=1', '_blank');
    if (win) win.opener = null;
    btn.disabled = true;
    btn.textContent = '여는 중';
    await ensureLink(item);
    const href = new URL(buyHref(item), location.href).href;
    if (win && !win.closed) win.location.replace(href);
    else location.href = href;
    render();
  });

  /* ---------- 백업 ---------- */
  $('m-export').addEventListener('click', () => {
    if (!state.items.length) return toast('아직 담은 상품이 없어요');
    const blob = new Blob([JSON.stringify({ app: 'sadagu-mine', v: 1, saved: new Date().toISOString(), items: state.items }, null, 1)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `sadagu-mine-${today()}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    toast('백업 파일을 저장했어요');
  });
  $('m-import').addEventListener('change', async (ev) => {
    const file = ev.target.files[0];
    ev.target.value = '';
    if (!file) return;
    try {
      const d = JSON.parse(await file.text());
      if (!d || d.app !== 'sadagu-mine' || !Array.isArray(d.items)) throw new Error('not ours');
      const have = new Set(state.items.map((x) => x.url));
      const added = d.items.map(clean).filter((x) => x && !have.has(x.url) && (have.add(x.url), true));
      state.items = [...added, ...state.items].slice(0, 200);
      save();
      render();
      toast(`${added.length}개를 불러왔어요`);
    } catch {
      toast("'내 상품' 백업 파일이 아니에요");
    }
  });

  document.addEventListener('sdg:noaff', render);
  render();
  loadCatalog();
})();
