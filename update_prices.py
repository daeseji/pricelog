"""싸다구 가격 확인 (GitHub Actions에서 매시간 실행)

쿠팡 파트너스 검색 API는 1시간에 약 10회까지만 허용된다는 사례가 있어요. 그래서
하루에 한 번 몰아서 부르지 않고, 30분마다 실행하면서 직전 62분 동안 부른 횟수를 빼고
남은 만큼(한 번에 최대 PER_RUN회, 1시간에 최대 PER_HOUR회)만 불러요. 하루 최대 PER_DAY회예요.

확인 순서
  1) 운영자 상품(data/products.json) 중 오늘 아직 확인하지 않은 것
  2) 방문자가 '내 상품'에서 '매일 확인'을 켠 상품(data/pool.json), 오래 확인 못 한 것부터
검색 결과 하나에 여러 상품이 들어 있으면, 상품 번호와 옵션 번호가 정확히 같은 상품은 모두 함께 기록해요.
다른 옵션(용량, 수량)의 가격은 기록하지 않아요.

안전장치
  - 실패하면 재시도하지 않고 바로 멈추고, PAUSE_HOURS 동안 부르지 않아요 (연속 오류로 차단되는 것 방지)
  - 쿠팡 검색어는 50자까지만 보내요 (넘으면 오류가 나요)
  - 같은 상품은 RETRY_HOURS 안에 다시 찾지 않고, GIVE_UP_MISSES번 연속 못 찾으면 7일에 한 번만 찾아요

사이트 반영
  매 실행 결과를 저장소에 올리되, Cloudflare Pages 빌드는 PUBLISH_HOURS에 한 번만 일어나게 해요
  (무료 플랜 빌드 한도 때문이에요). 워크플로가 GITHUB_OUTPUT의 publish 값으로 커밋 메시지를 고르고,
  publish가 아니면 메시지에 [CF-Pages-Skip]을 붙여요.
"""
import datetime
import hashlib
import hmac
import json
import os
import re
import time
import urllib.parse
from time import gmtime, strftime

import requests

ACCESS_KEY = os.environ.get("COUPANG_ACCESS_KEY", "")
SECRET_KEY = os.environ.get("COUPANG_SECRET_KEY", "")
# '매일 확인' 신청 목록을 주는 주소 (Google Apps Script 웹 앱 + ?action=pool, worker/README.md 참고)
POOL_URL = os.environ.get("SADAGU_POOL_URL", "")
DOMAIN = "https://api-gateway.coupang.com"
SEARCH_PATH = "/v2/providers/affiliate_open_api/apis/openapi/v1/products/search"

PER_HOUR = 9
PER_RUN = 5
PER_DAY = 200
WINDOW_HOURS = 62 / 60
CALL_GAP = 40
PAUSE_HOURS = 2
PUBLISH_HOURS = 12
RETRY_HOURS = 3
GIVE_UP_MISSES = 3
GIVE_UP_DAYS = 7
SEARCH_LIMIT = 10
HISTORY_LIMIT = 365
POOL_HISTORY_LIMIT = 120
POOL_KEEP_DAYS = 90

PRODUCTS = "data/products.json"
PRICES = "data/prices.json"
POOL = "data/pool.json"
STATE = "data/state.json"
KST = datetime.timezone(datetime.timedelta(hours=9))
FMT = "%Y-%m-%d %H:%M"
CALL_FMT = "%Y-%m-%d %H:%M:%S"


def generateHmac(method, url, secretKey, accessKey):
    path, *query = url.split("?")
    datetimeGMT = strftime('%y%m%d', gmtime()) + 'T' + strftime('%H%M%S', gmtime()) + 'Z'
    message = datetimeGMT + method + path + (query[0] if query else "")
    signature = hmac.new(bytes(secretKey, "utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return "CEA algorithm=HmacSHA256, access-key={}, signed-date={}, signature={}".format(accessKey, datetimeGMT, signature)


def normalize(name):
    # 띄어쓰기·쉼표 등 기호를 빼고 비교 (예: "우유, 900ml" == "우유 900ml")
    s = re.sub(r"[\s,.\-_/()\[\]]", "", str(name)).lower()
    # 끝의 "1개"는 있어도 없어도 같은 상품으로 봅니다
    return re.sub(r"(?<!\d)1개$", "", s)


class ApiError(Exception):
    pass


def search(keyword):
    keyword = str(keyword)[:50]  # 쿠팡 검색어는 50자까지 (넘으면 오류로 그날 수집이 멈춰요)
    qs = urllib.parse.urlencode({"keyword": keyword, "limit": SEARCH_LIMIT}, quote_via=urllib.parse.quote)
    url = SEARCH_PATH + "?" + qs
    auth = generateHmac("GET", url, SECRET_KEY, ACCESS_KEY)
    r = requests.get(DOMAIN + url, headers={"Authorization": auth, "Content-Type": "application/json"}, timeout=15)
    if r.status_code != 200:
        raise ApiError(f"HTTP {r.status_code}: {r.text[:200]}")
    body = r.json()
    if str(body.get("rCode")) != "0":
        raise ApiError(f"rCode {body.get('rCode')}: {str(body.get('rMessage'))[:200]}")
    return body.get("data", {}).get("productData", []) or []


def item_id(p):
    # 검색 결과 링크에 들어 있는 옵션 번호(itemId)
    m = re.search(r"[?&]itemId=(\d+)", str(p.get("productUrl", "")))
    return m.group(1) if m else None


def find_product(product, results, saved_item):
    # 옵션 번호를 모르는 운영자 상품만 쓰는 방법이에요: 옵션까지 똑같은 상품명일 때만 받아요.
    # 옵션 없이 나오는 대표 상품명은 어느 용량·수량인지 알 수 없어서 받지 않아요.
    wanted = str(product.get("item_id") or saved_item or "")
    if wanted:
        for p in results:
            if item_id(p) == wanted:
                return p
        return None
    full = normalize(product.get("title") or product["name"])
    for p in results:
        if normalize(p.get("productName", "")) == full:
            return p
    return None


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_time(s):
    for fmt in (CALL_FMT, FMT):
        try:
            return datetime.datetime.strptime(str(s), fmt).replace(tzinfo=KST)
        except (TypeError, ValueError):
            continue
    return None


def hours_since(s, now):
    t = parse_time(s)
    return (now - t).total_seconds() / 3600 if t else 1e9


def as_price(v):
    try:
        n = int(round(float(v)))
    except (TypeError, ValueError):
        return 0
    return n if 0 < n < 1_000_000_000 else 0


def pool_keywords(title):
    # 다시 구매 화면의 이름은 "상품명, 용량, 수량" 모양이에요. 옵션을 붙이면 쿠팡 API가 엉뚱한 결과를 줄 때가 있어서
    # 상품명만 → 괄호를 뺀 상품명 → 전체 이름 순서로 바꿔 가며 찾아요.
    base = str(title).split(",")[0].strip()
    plain = re.sub(r"\s*\([^)]*\)", "", base).strip()
    out = []
    for k in (base, plain, str(title)):
        k = k[:50].strip()
        if k and k not in out:
            out.append(k)
    return out


def sync_pool(pool, today):
    """Apps Script에 모인 '매일 확인' 신청 목록을 pool.json에 반영해요."""
    items = pool.setdefault("items", {})
    if not POOL_URL:
        print("ℹ️ SADAGU_POOL_URL이 없어서 '매일 확인' 목록은 지난 목록 그대로 써요.")
        return
    try:
        r = requests.get(POOL_URL, timeout=30)
        r.raise_for_status()
        rows = r.json().get("items") or []
    except (requests.RequestException, ValueError, AttributeError) as e:
        print(f"⚠️ '매일 확인' 목록을 받지 못했어요. 이번에는 지난 목록으로 확인해요: {e}")
        return
    live = set()
    for row in rows:
        if not isinstance(row, list) or len(row) < 4:
            continue
        pid, item, vid, title = (str(x or "") for x in row[:4])
        title = re.sub(r"\s+", " ", title).strip()[:100]
        if not re.fullmatch(r"\d{3,15}", pid) or not re.fullmatch(r"\d{1,15}", item) or not title:
            continue
        key = f"{pid}:{item}"
        live.add(key)
        it = items.setdefault(key, {"h": [], "added": today})
        it["t"] = title
        if re.fullmatch(r"\d{1,15}", vid):
            it["v"] = vid
        seen = str(row[5] if len(row) > 5 else today)[:10]
        it["seen"] = seen if re.fullmatch(r"\d{4}-\d{2}-\d{2}", seen) else today
        it["on"] = True
    cutoff = (datetime.datetime.strptime(today, "%Y-%m-%d") - datetime.timedelta(days=POOL_KEEP_DAYS)).strftime("%Y-%m-%d")
    for key in list(items):
        if key in live:
            continue
        items[key]["on"] = False
        if (items[key].get("seen") or "") < cutoff:
            del items[key]
    print(f"📋 '매일 확인' 신청 상품 {len(live)}개")


def main(search_fn=search, clock=None, sleep=time.sleep):
    clock = clock or (lambda: datetime.datetime.now(KST))
    now = clock()
    today = now.strftime("%Y-%m-%d")
    stamp = now.strftime(FMT)

    products = load(PRODUCTS, {"products": []})["products"]
    prices = load(PRICES, {})
    history = prices.setdefault("history", {})
    meta = prices.setdefault("meta", {})
    pool = load(POOL, {"items": {}})
    pitems = pool.setdefault("items", {})
    state = load(STATE, {})
    cstate = state.setdefault("catalog", {})

    before = json.dumps(pool, sort_keys=True, ensure_ascii=False)
    sync_pool(pool, today)
    pool_changed = json.dumps(pool, sort_keys=True, ensure_ascii=False) != before

    # ---------- 이번 실행에서 부를 수 있는 횟수 ----------
    calls = [c for c in state.get("calls", []) if hours_since(c, now) < 24.5]
    recent = sum(1 for c in calls if hours_since(c, now) < WINDOW_HOURS)
    today_calls = sum(1 for c in calls if str(c).startswith(today))
    budget = max(0, min(PER_RUN, PER_HOUR - recent, PER_DAY - today_calls))
    if hours_since(state.get("pause_until"), now) < 0:
        print(f"⏸ API 오류 뒤 쉬는 중이에요 ({state['pause_until']}까지).")
        budget = 0
    print(f"🔢 직전 62분 {recent}회, 오늘 {today_calls}회 불렀어요. 이번 실행은 최대 {budget}회예요.")

    # ---------- 같은 상품(옵션까지)을 찾기 위한 색인 ----------
    catalog_by_key = {}
    for p in products:
        m = re.search(r"/products/(\d+)", str(p.get("url", "")))
        if m and p.get("item_id"):
            catalog_by_key[f"{m.group(1)}:{p['item_id']}"] = p["name"]
        last = (history.get(p["name"]) or [{}])[-1]
        st = cstate.setdefault(p["name"], {})
        if str(last.get("date", "")).startswith(today):
            st["ok"] = today

    changed = False

    def record_catalog(name, match):
        price = as_price(match.get("productPrice"))
        if not price:
            return False
        entries = [e for e in history.get(name, []) if not str(e.get("date", "")).startswith(today)]
        entries.append({"date": stamp, "price": price})
        history[name] = entries[-HISTORY_LIMIT:]
        meta[name] = {
            **{k: v for k, v in meta.get(name, {}).items() if k == "localImage"},
            "productId": match.get("productId"),
            "itemId": item_id(match),
            "productName": match.get("productName"),
            "image": match.get("productImage"),
            "rocket": bool(match.get("isRocket")),
            "freeShipping": bool(match.get("isFreeShipping")),
            # 검색 결과의 상품 링크는 싸다구 파트너스 계정의 제휴 링크라서 그대로 저장해요
            "link": match.get("productUrl"),
        }
        st = cstate.setdefault(name, {})
        st.update(ok=today, miss=0)
        print(f"  ✅ [운영자] {name}: {price:,}원")
        return True

    def record_pool(key, match):
        price = as_price(match.get("productPrice"))
        it = pitems.get(key)
        if not price or it is None:
            return False
        h = [e for e in it.get("h", []) if e[0] != today]
        h.append([today, price])
        it["h"] = h[-POOL_HISTORY_LIMIT:]
        it.update(ok=today, miss=0, name=str(match.get("productName") or "")[:100], link=match.get("productUrl") or "")
        print(f"  ✅ [매일 확인] {it.get('t', key)}: {price:,}원")
        return True

    def take_results(results):
        """검색 결과에서 옵션까지 같은 상품을 모두 기록하고, 기록한 키 목록을 돌려줘요."""
        nonlocal changed
        hit = set()
        for p in results:
            key = f"{p.get('productId')}:{item_id(p)}"
            name = catalog_by_key.get(key)
            if name and cstate.get(name, {}).get("ok") != today and record_catalog(name, p):
                hit.add(("c", name))
                changed = True
            it = pitems.get(key)
            if it is not None and it.get("ok") != today and record_pool(key, p):
                hit.add(("p", key))
                changed = True
        return hit

    # ---------- 오늘 확인할 순서 ----------
    tasks = []
    for p in products:
        st = cstate[p["name"]]
        # 운영자 상품은 하루에 두 번까지만 찾아요 (못 찾는 상품이 호출을 다 쓰지 않게)
        tries_today = st.get("n", 0) if str(st.get("try", "")).startswith(today) else 0
        if st.get("ok") == today or tries_today >= 2 or hours_since(st.get("try"), now) < RETRY_HOURS:
            continue
        kws = [p.get("keyword") or p.get("title") or p["name"]]
        for k in [p["name"], *(p.get("fallback_keywords") or [])]:
            if k and k not in kws:
                kws.append(k)
        tasks.append(("c", p, kws))
    pool_due = []
    for key, it in pitems.items():
        if not it.get("on") or key in catalog_by_key or it.get("ok") == today:
            continue
        since = hours_since(it.get("try"), now)
        if since < RETRY_HOURS or (it.get("miss", 0) >= GIVE_UP_MISSES and since < GIVE_UP_DAYS * 24):
            continue
        pool_due.append((it.get("ok") or "", it.get("added") or "", key))
    pool_due.sort()
    tasks += [("p", key, None) for _, _, key in pool_due]
    print(f"📝 확인할 상품: 운영자 {sum(1 for t in tasks if t[0] == 'c')}개, 매일 확인 {len(pool_due)}개")

    # ---------- 확인 ----------
    used = 0

    def call(kw):
        nonlocal used
        if used > 0:
            sleep(CALL_GAP)
        used += 1
        calls.append(clock().strftime(CALL_FMT))
        return search_fn(kw)

    stopped = False
    for kind, ref, kws in tasks:
        if used >= budget or stopped:
            break
        if kind == "c":
            name = ref["name"]
            st = cstate[name]
            if st.get("ok") == today:  # 다른 상품을 찾다가 함께 기록됐어요
                continue
            st["n"] = (st.get("n", 0) if str(st.get("try", "")).startswith(today) else 0) + 1
            st["try"] = stamp
            found = False
            for kw in kws:
                if used >= budget:
                    break
                print(f"\n조회: [운영자] {name}  (검색어: {kw})")
                try:
                    results = call(kw)
                except ApiError as e:
                    print(f"  ⛔ API 오류로 여기서 멈춰요 (재시도 안 함): {e}")
                    state["pause_until"] = (now + datetime.timedelta(hours=PAUSE_HOURS)).strftime(FMT)
                    stopped = True
                    break
                hit = take_results(results)
                if ("c", name) in hit:
                    found = True
                    break
                if not ref.get("item_id"):
                    m = find_product(ref, results, meta.get(name, {}).get("itemId"))
                    if m is not None and record_catalog(name, m):
                        changed = found = True
                        break
                print("  ❌ 이 검색어로는 같은 상품(옵션)을 못 찾았어요.")
            if not found and not stopped:
                st["miss"] = st.get("miss", 0) + 1
        else:
            it = pitems[ref]
            if it.get("ok") == today:
                continue
            kws = pool_keywords(it.get("t", ""))
            kw = kws[it.get("kw", 0) % len(kws)]
            it["try"] = stamp
            print(f"\n조회: [매일 확인] {it.get('t')}  (검색어: {kw})")
            try:
                results = call(kw)
            except ApiError as e:
                print(f"  ⛔ API 오류로 여기서 멈춰요 (재시도 안 함): {e}")
                state["pause_until"] = (now + datetime.timedelta(hours=PAUSE_HOURS)).strftime(FMT)
                stopped = True
                break
            if ("p", ref) not in take_results(results):
                it["miss"] = it.get("miss", 0) + 1
                it["kw"] = (it.get("kw", 0) + 1) % len(kws)
                print("  ❌ 이 검색어로는 같은 상품(옵션)을 못 찾았어요. 다음에는 다른 검색어로 찾아요.")
        changed = True  # 시도 기록(try, miss)도 저장해요

    # ---------- 저장과 사이트 반영 ----------
    if used == 0 and not changed and not pool_changed:
        print("\n이번에는 부를 수 있는 횟수나 확인할 상품이 없어서 저장하지 않았어요.")
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a", encoding="utf-8") as f:
                f.write("publish=false\n")
        return {"used": 0, "publish": False}
    state["calls"] = calls[-(PER_DAY + 20):]
    if changed or pool_changed:
        state["dirty"] = True
    publish = bool(state.get("dirty")) and hours_since(state.get("published"), now) >= PUBLISH_HOURS
    if publish:
        state["published"] = stamp
        state["dirty"] = False
    pool["updated"] = stamp
    save(PRICES, prices)
    save(POOL, pool)
    save(STATE, state)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"publish={'true' if publish else 'false'}\n")
    print(f"\n저장 완료! 이번 실행 {used}회 호출 · 사이트 반영 {'함' if publish else '다음에'}")
    return {"used": used, "publish": publish}


if __name__ == "__main__":
    main()
