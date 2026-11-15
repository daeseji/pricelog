/**
 * 싸다구 제휴 링크 서버 (Google Apps Script 웹 앱)
 *
 * 하는 일
 *   방문자가 '내 상품'에서 '쿠팡에서 보기'를 누르면, 그 상품 주소를 쿠팡 파트너스 딥링크 API로 보내
 *   싸다구의 제휴 링크를 받아 돌려줘요. 쿠팡 페이지를 대신 열거나 클릭하지 않아요.
 *
 * 설정
 *   프로젝트 설정 > 스크립트 속성: COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY
 *   배포 > 새 배포 > 웹 앱 (실행 사용자: 나, 액세스 권한: 모든 사용자)
 *
 * 매일 확인 목록 (pool)
 *   방문자가 '내 상품'에서 '매일 확인'을 켜면 상품 번호, 옵션 번호, 판매 옵션 번호, 상품 이름만 받아 모아 둬요.
 *   누가 보냈는지는 남기지 않아요. GitHub Actions(update_prices.py)가 ?action=pool로 목록을 받아 가격을 확인해요.
 *   POOL_DAYS 동안 아무도 다시 신청하지 않은 상품은 빠지고, 최대 POOL_MAX개까지만 모아요.
 *
 * 안전장치
 *   - 쿠팡 상품 페이지 주소만 받아요. 줄인 주소는 열어 보지 않아요 (열면 그 링크의 클릭으로 잡힐 수 있어요).
 *   - 새 링크는 전체 합쳐 시간당 PER_HOUR개, 하루 PER_DAY개까지만 만들어요.
 *   - 쿠팡 API가 오류를 돌려주면 한 시간 동안 새 링크를 만들지 않아요 (연속 오류로 키가 막히지 않게).
 *   - 한 번 만든 링크는 6시간 동안 기억해서 같은 상품은 다시 부르지 않아요.
 *   - 링크는 POST 요청으로만 만들어요. 검색 로봇이 주소를 열어도 아무것도 만들지 않아요.
 */
const API = 'https://api-gateway.coupang.com';
const DEEPLINK = '/v2/providers/affiliate_open_api/apis/openapi/v1/deeplink';
const PER_HOUR = 20;
const PER_DAY = 150;
const PRODUCT_HOSTS = ['www.coupang.com', 'coupang.com', 'm.coupang.com'];
const LINK_RE = /^https:\/\/(link\.coupang\.com|coupa\.ng)\/[A-Za-z0-9/_?=&.-]+$/;
const POOL_MAX = 1000;
const POOL_DAYS = 60;
const POOL_CHUNK = 8000; // 스크립트 속성 한 칸은 9KB까지라서 나눠 담아요

function doGet(e) {
  const p = (e && e.parameter) || {};
  if (p.action === 'pool') return out_({ items: loadPool_() });
  return out_({ ok: true, service: 'sadagu-link' });
}

function doPost(e) {
  let body = null;
  try {
    body = JSON.parse((e && e.postData && e.postData.contents) || '');
  } catch (err) {
    body = null;
  }
  if (body && body.action === 'track') return out_(track_(body.items));
  if (!body || typeof body.url !== 'string') return out_({ error: 'bad_request' });
  return out_(handle_(body.url));
}

/** '매일 확인' 신청을 받아요. 상품 번호, 옵션 번호, 판매 옵션 번호, 이름만 남겨요 */
function track_(items) {
  if (!Array.isArray(items)) return { error: 'bad_request' };
  const today = Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyy-MM-dd');
  const got = [];
  items.slice(0, 300).forEach(function (r) {
    if (!Array.isArray(r)) return;
    const pid = String(r[0] || '');
    const item = String(r[1] || '');
    const vid = String(r[2] || '');
    const title = String(r[3] || '').replace(/\s+/g, ' ').trim().slice(0, 80);
    if (!/^\d{3,15}$/.test(pid) || !/^\d{1,15}$/.test(item) || (vid && !/^\d{1,15}$/.test(vid)) || !title) return;
    got.push([pid, item, vid, title]);
  });
  if (!got.length) return { error: 'no_items' };
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) return { error: 'busy' };
  try {
    const pool = loadPool_();
    const at = {};
    pool.forEach(function (r, i) {
      at[r[0] + ':' + r[1]] = i;
    });
    let added = 0;
    got.forEach(function (g) {
      const k = g[0] + ':' + g[1];
      if (k in at) {
        const r = pool[at[k]];
        r[2] = g[2] || r[2];
        r[3] = g[3];
        r[5] = today;
      } else {
        at[k] = pool.length;
        pool.push([g[0], g[1], g[2], g[3], today, today]);
        added++;
      }
    });
    // 오래 신청이 없던 상품을 빼고, 많으면 최근에 신청된 순서로 POOL_MAX개만 남겨요
    const cutoff = Utilities.formatDate(new Date(Date.now() - POOL_DAYS * 864e5), 'Asia/Seoul', 'yyyy-MM-dd');
    let kept = pool.filter(function (r) {
      return String(r[5]) >= cutoff;
    });
    if (kept.length > POOL_MAX) {
      kept.sort(function (a, b) {
        return String(b[5]).localeCompare(String(a[5]));
      });
      kept = kept.slice(0, POOL_MAX);
    }
    savePool_(kept);
    return { ok: true, added: added, total: kept.length };
  } finally {
    lock.releaseLock();
  }
}

function loadPool_() {
  const all = PropertiesService.getScriptProperties().getProperties();
  const n = Number(all.POOL_N || 0);
  let out = [];
  for (let i = 0; i < n; i++) {
    try {
      out = out.concat(JSON.parse(all['POOL_' + i] || '[]'));
    } catch (err) {
      // 깨진 칸은 건너뛰어요
    }
  }
  return out;
}

function savePool_(pool) {
  const props = PropertiesService.getScriptProperties();
  const chunks = [];
  let cur = [];
  let size = 2;
  pool.forEach(function (r) {
    const s = JSON.stringify(r);
    const b = Utilities.newBlob(s).getBytes().length + 1;
    if (cur.length && size + b > POOL_CHUNK) {
      chunks.push(cur);
      cur = [];
      size = 2;
    }
    cur.push(r);
    size += b;
  });
  if (cur.length) chunks.push(cur);
  const old = Number(props.getProperty('POOL_N') || 0);
  const data = { POOL_N: String(chunks.length) };
  chunks.forEach(function (c, i) {
    data['POOL_' + i] = JSON.stringify(c);
  });
  props.setProperties(data);
  for (let i = chunks.length; i < old; i++) props.deleteProperty('POOL_' + i);
}

function handle_(raw) {
  const target = parse_(raw);
  if (!target) return { error: 'invalid_url' };

  const cache = CacheService.getScriptCache();
  const hit = cache.get('l:' + target.key);
  if (hit) return { link: hit, product: target.url, cached: true };

  const props = PropertiesService.getScriptProperties();
  const ak = props.getProperty('COUPANG_ACCESS_KEY');
  const sk = props.getProperty('COUPANG_SECRET_KEY');
  if (!ak || !sk) return { error: 'not_configured' };
  if (cache.get('pause')) return { error: 'busy' };
  if (!take_(props)) return { error: 'busy' };

  let res;
  try {
    res = UrlFetchApp.fetch(API + DEEPLINK, {
      method: 'post',
      contentType: 'application/json',
      headers: { Authorization: auth_('POST', DEEPLINK, ak, sk) },
      payload: JSON.stringify({ coupangUrls: [target.url] }),
      muteHttpExceptions: true,
      followRedirects: false,
    });
  } catch (err) {
    cache.put('pause', '1', 600);
    return { error: 'upstream' };
  }
  const status = res.getResponseCode();
  if (status !== 200) {
    // 인증, 호출 한도, 쿠팡 서버 문제: 한 시간 쉬어요
    cache.put('pause', '1', 3600);
    return { error: 'upstream' };
  }
  let data = null;
  try {
    data = JSON.parse(res.getContentText());
  } catch (err) {
    data = null;
  }
  const link = data && data.data && data.data[0] && data.data[0].shortenUrl;
  if (!data || String(data.rCode) !== '0' || !LINK_RE.test(link || '')) return { error: 'no_link' };
  cache.put('l:' + target.key, link, 21600);
  return { link: link, product: target.url };
}

/** 쿠팡 상품 페이지 주소만 받아 같은 모양으로 정리해요 (숫자가 아닌 값과 추적 파라미터는 버려요) */
function parse_(raw) {
  const s = String(raw || '').trim();
  if (s.length > 2000) return null;
  const m = s.match(/^https?:\/\/([^\/?#]+)(\/[^?#]*)?(?:\?([^#]*))?/i);
  if (!m) return null;
  const host = m[1].toLowerCase();
  const path = m[2] || '/';
  const params = {};
  (m[3] || '').split('&').forEach(function (kv) {
    if (!kv) return;
    const i = kv.indexOf('=');
    const k = i < 0 ? kv : kv.slice(0, i);
    if (!(k in params)) params[k] = i < 0 ? '' : kv.slice(i + 1);
  });
  let id = '';
  if (PRODUCT_HOSTS.indexOf(host) >= 0) {
    const pm = path.match(/^\/(?:vp|vm)\/products\/(\d{3,15})/);
    id = pm ? pm[1] : '';
  } else if (host === 'link.coupang.com' && path.indexOf('/re/') === 0) {
    // 상품 번호(pageKey)가 주소에 그대로 적힌 긴 링크는 열지 않고 읽어요
    id = /^\d{3,15}$/.test(params.pageKey || '') ? params.pageKey : '';
  }
  if (!id) return null;
  const digits = function (v) {
    return /^\d{1,15}$/.test(v || '') ? v : '';
  };
  const itemId = digits(params.itemId);
  const vendorItemId = digits(params.vendorItemId);
  const q = [];
  if (itemId) q.push('itemId=' + itemId);
  if (vendorItemId) q.push('vendorItemId=' + vendorItemId);
  return {
    key: 'p' + id + '-i' + itemId + '-v' + vendorItemId,
    url: 'https://www.coupang.com/vp/products/' + id + (q.length ? '?' + q.join('&') : ''),
  };
}

/** 전체 호출 수를 시간·하루 단위로 세요. 넘으면 false */
function take_(props) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) return false;
  try {
    const now = new Date();
    const hour = Utilities.formatDate(now, 'Asia/Seoul', 'yyyyMMddHH');
    const day = hour.slice(0, 8);
    let q = {};
    try {
      q = JSON.parse(props.getProperty('QUOTA') || '{}');
    } catch (err) {
      q = {};
    }
    const nh = q.h === hour ? q.nh : 0;
    const nd = q.d === day ? q.nd : 0;
    if (nh >= PER_HOUR || nd >= PER_DAY) return false;
    props.setProperty('QUOTA', JSON.stringify({ h: hour, nh: nh + 1, d: day, nd: nd + 1 }));
    return true;
  } finally {
    lock.releaseLock();
  }
}

function auth_(method, path, ak, sk) {
  const signedDate = Utilities.formatDate(new Date(), 'GMT', "yyMMdd'T'HHmmss'Z'");
  const sig = Utilities.computeHmacSha256Signature(signedDate + method + path, sk, Utilities.Charset.UTF_8);
  const hex = sig
    .map(function (b) {
      return ('0' + (b & 0xff).toString(16)).slice(-2);
    })
    .join('');
  return 'CEA algorithm=HmacSHA256, access-key=' + ak + ', signed-date=' + signedDate + ', signature=' + hex;
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

/** 편집기에서 직접 실행해 설정을 확인해요 (키 값은 출력하지 않아요) */
function checkSetup() {
  const props = PropertiesService.getScriptProperties();
  Logger.log('키 설정: access %s, secret %s', props.getProperty('COUPANG_ACCESS_KEY') ? '있음' : '없음', props.getProperty('COUPANG_SECRET_KEY') ? '있음' : '없음');
  Logger.log('오늘 사용량: %s', props.getProperty('QUOTA') || '없음');
  Logger.log('매일 확인 목록: %s개', loadPool_().length);
}
