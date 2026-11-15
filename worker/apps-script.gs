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

function doGet() {
  return out_({ ok: true, service: 'sadagu-link' });
}

function doPost(e) {
  let body = null;
  try {
    body = JSON.parse((e && e.postData && e.postData.contents) || '');
  } catch (err) {
    body = null;
  }
  if (!body || typeof body.url !== 'string') return out_({ error: 'bad_request' });
  return out_(handle_(body.url));
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
}
