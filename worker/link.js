/**
 * 싸다구 제휴 링크 서버 (Cloudflare Workers 버전)
 *
 * 지금 쓰는 서버는 같은 폴더의 apps-script.gs(Google Apps Script)예요.
 * 나중에 Cloudflare로 옮기고 싶을 때 이 파일을 쓰면 돼요. 하는 일과 안전장치는 같아요.
 *
 * 하는 일
 *   방문자가 '내 상품'에서 '쿠팡에서 보기'를 누르면, 그 상품 주소를 쿠팡 파트너스 딥링크 API로 보내
 *   싸다구의 제휴 링크를 받아 돌려줘요. 쿠팡 페이지를 대신 열거나 클릭하지 않아요.
 *
 * 설정 (Workers > 이 Worker > Settings > Variables and Secrets)
 *   COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY  비밀값(Secret)으로 넣어요
 *   LINKS (선택)  KV 네임스페이스 바인딩. 만든 링크를 오래 저장해 API 호출을 줄여요
 */

const ALLOWED_ORIGINS = ["https://daeseji.github.io"];
const PRODUCT_HOSTS = new Set(["www.coupang.com", "coupang.com", "m.coupang.com"]);
const API = "https://api-gateway.coupang.com";
const DEEPLINK = "/v2/providers/affiliate_open_api/apis/openapi/v1/deeplink";
const LINK_RE = /^https:\/\/(link\.coupang\.com|coupa\.ng)\/[A-Za-z0-9/_?=&.-]+$/;
const PER_IP_PER_HOUR = 10;
const PER_HOUR = 20; // 이 인스턴스 전체 합계

const memory = new Map(); // 같은 인스턴스 안의 짧은 캐시
const hits = new Map(); // IP별 시간당 요청 수
let total = { hour: -1, n: 0 };
let pausedUntil = 0;

function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0],
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

function reply(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders(origin), "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

/** 쿠팡 상품 페이지 주소만 받아 같은 모양으로 정리해요. 줄인 주소는 열어 보지 않아요 (열면 그 링크의 클릭으로 잡힐 수 있어요) */
function normalize(raw) {
  let u;
  try {
    u = new URL(String(raw || "").trim());
  } catch {
    return null;
  }
  if (!/^https?:$/.test(u.protocol)) return null;
  let id = "";
  if (PRODUCT_HOSTS.has(u.hostname)) {
    id = (u.pathname.match(/^\/(?:vp|vm)\/products\/(\d{3,15})/) || [])[1] || "";
  } else if (u.hostname === "link.coupang.com" && u.pathname.startsWith("/re/")) {
    const k = u.searchParams.get("pageKey") || "";
    id = /^\d{3,15}$/.test(k) ? k : "";
  }
  if (!id) return null;
  const digits = (v) => (/^\d{1,15}$/.test(v || "") ? v : "");
  const itemId = digits(u.searchParams.get("itemId"));
  const vendorItemId = digits(u.searchParams.get("vendorItemId"));
  const q = new URLSearchParams();
  if (itemId) q.set("itemId", itemId);
  if (vendorItemId) q.set("vendorItemId", vendorItemId);
  const qs = q.toString();
  return {
    key: `p${id}-i${itemId}-v${vendorItemId}`,
    url: `https://www.coupang.com/vp/products/${id}${qs ? "?" + qs : ""}`,
  };
}

async function authorization(method, path, accessKey, secretKey) {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  const signedDate = `${String(d.getUTCFullYear()).slice(-2)}${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}T${p(d.getUTCHours())}${p(d.getUTCMinutes())}${p(d.getUTCSeconds())}Z`;
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", enc.encode(secretKey), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(signedDate + method + path)));
  const hex = Array.from(sig, (b) => b.toString(16).padStart(2, "0")).join("");
  return `CEA algorithm=HmacSHA256, access-key=${accessKey}, signed-date=${signedDate}, signature=${hex}`;
}

function allowed(ip) {
  const hour = Math.floor(Date.now() / 3600000);
  if (total.hour !== hour) total = { hour, n: 0 };
  if (total.n >= PER_HOUR) return false;
  const cur = hits.get(ip);
  if (!cur || cur.hour !== hour) {
    if (hits.size > 5000) hits.clear();
    hits.set(ip, { hour, n: 1 });
  } else {
    if (cur.n >= PER_IP_PER_HOUR) return false;
    cur.n += 1;
  }
  total.n += 1;
  return true;
}

function remember(key, link) {
  if (memory.size > 2000) memory.delete(memory.keys().next().value);
  memory.set(key, link);
}

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin") || "";
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders(origin) });
    if (request.method === "GET") return reply({ ok: true, service: "sadagu-link" }, 200, origin);
    if (request.method !== "POST") return reply({ error: "method_not_allowed" }, 405, origin);
    if (!ALLOWED_ORIGINS.includes(origin)) return reply({ error: "forbidden_origin" }, 403, origin);
    if (!env.COUPANG_ACCESS_KEY || !env.COUPANG_SECRET_KEY) return reply({ error: "not_configured" }, 503, origin);

    let body;
    try {
      body = JSON.parse(await request.text()); // 일반 텍스트로 와도 읽어요
    } catch {
      return reply({ error: "bad_request" }, 400, origin);
    }
    const target = normalize(body && body.url);
    if (!target) return reply({ error: "invalid_url" }, 400, origin);

    const inMemory = memory.get(target.key);
    if (inMemory) return reply({ link: inMemory, product: target.url, cached: true }, 200, origin);
    if (env.LINKS) {
      const stored = await env.LINKS.get(target.key);
      if (stored) {
        remember(target.key, stored);
        return reply({ link: stored, product: target.url, cached: true }, 200, origin);
      }
    }

    if (Date.now() < pausedUntil) return reply({ error: "busy" }, 503, origin);
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    if (!allowed(ip)) return reply({ error: "busy" }, 429, origin);

    try {
      const res = await fetch(API + DEEPLINK, {
        method: "POST",
        headers: {
          Authorization: await authorization("POST", DEEPLINK, env.COUPANG_ACCESS_KEY, env.COUPANG_SECRET_KEY),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ coupangUrls: [target.url] }),
        redirect: "manual",
      });
      if (res.status !== 200) {
        pausedUntil = Date.now() + 3600000; // 인증, 호출 한도, 쿠팡 서버 문제: 한 시간 쉬어요
        return reply({ error: "upstream" }, 502, origin);
      }
      const data = await res.json().catch(() => null);
      const link = data && Array.isArray(data.data) && data.data[0] && data.data[0].shortenUrl;
      if (!data || String(data.rCode) !== "0" || !LINK_RE.test(link || "")) return reply({ error: "no_link" }, 502, origin);
      remember(target.key, link);
      if (env.LINKS) ctx.waitUntil(env.LINKS.put(target.key, link));
      return reply({ link, product: target.url }, 200, origin);
    } catch {
      pausedUntil = Date.now() + 600000;
      return reply({ error: "upstream" }, 502, origin);
    }
  },
};
