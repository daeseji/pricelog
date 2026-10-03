import json, hmac, hashlib, requests, urllib.parse, os, re, time, datetime
from time import gmtime, strftime

ACCESS_KEY = os.environ["COUPANG_ACCESS_KEY"]
SECRET_KEY = os.environ["COUPANG_SECRET_KEY"]
DOMAIN = "https://api-gateway.coupang.com"
SEARCH_PATH = "/v2/providers/affiliate_open_api/apis/openapi/v1/products/search"

# 🛡 쿠팡 파트너스 호출 제한 보호 장치
# - 검색 API는 실제로 1시간에 약 10회까지만 허용된다는 사례가 있어서
#   호출 사이에 400초(6분 40초)씩 쉬어 1시간에 최대 9회만 호출합니다.
# - 한 번 실행할 때 최대 MAX_CALLS_PER_RUN 번까지만 호출합니다.
# - 실패하면 재시도하지 않고 바로 멈춥니다. (연속 오류로 차단되는 것 방지)
DELAY_SECONDS = 400
MAX_CALLS_PER_RUN = 20
SEARCH_LIMIT = 10
HISTORY_LIMIT = 365


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
    # 정확히 같은 상품(같은 옵션)일 때만 가격을 기록합니다.
    # 1) products.json의 item_id 또는 지난번에 찾은 옵션 번호 → 그 옵션만
    # 2) 옵션까지 똑같은 상품명 (예: "코카콜라 오리지널, 2L, 8개")
    # 옵션 없이 나오는 대표 상품명("제주삼다수 그린 무라벨")은 어느 용량·수량인지 알 수 없어서
    # 받지 않아요. 다른 옵션 가격이 기록되는 것보다 기록을 건너뛰는 게 나아요.
    wanted = str(product.get("item_id") or saved_item or "")
    if wanted:
        for p in results:
            if item_id(p) == wanted:
                return p
        return None  # 다른 옵션 가격이 섞이지 않게, 못 찾으면 기록하지 않아요
    title = product.get("title") or product["name"]
    full = normalize(title)
    for p in results:
        if normalize(p.get("productName", "")) == full:
            return p
    return None


def main():
    with open("data/products.json", "r", encoding="utf-8") as f:
        products = json.load(f)["products"]
    with open("data/prices.json", "r", encoding="utf-8") as f:
        prices = json.load(f)
    history = prices.setdefault("history", {})
    meta = prices.setdefault("meta", {})

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")

    if len(products) > MAX_CALLS_PER_RUN:
        print(f"⚠️ 상품이 {len(products)}개예요. 안전을 위해 앞의 {MAX_CALLS_PER_RUN}개만 조회합니다.")
        products = products[:MAX_CALLS_PER_RUN]

    for i, product in enumerate(products):
        if i > 0:
            time.sleep(DELAY_SECONDS)
        print(f"\n조회 중 ({i + 1}/{len(products)}): {product['name']}")
        try:
            # 쿠팡 파트너스에서 검색하듯 상품명(옵션까지) 그대로 검색해요
            results = search(product.get("keyword") or product.get("title") or product["name"])
        except ApiError as e:
            print(f"  ⛔ API 오류로 여기서 멈춥니다 (재시도 안 함): {e}")
            break

        key = product["name"]
        match = find_product(product, results, meta.get(key, {}).get("itemId"))
        if match is None:
            print("  ❌ 검색 결과에서 같은 상품(옵션)을 못 찾아서 기록하지 않았어요. 검색 결과:")
            for p in results:
                print(f"     - [상품 {p.get('productId')} / 옵션 {item_id(p)}] {p.get('productName')} / {p.get('productPrice')}원")
            continue

        price = match.get("productPrice")
        if not price:
            print("  ❌ 가격 정보가 없어서 기록하지 않았어요.")
            continue
        entries = history.setdefault(key, [])
        entries.append({"date": now, "price": price})
        history[key] = entries[-HISTORY_LIMIT:]
        # 상품 사진·ID도 같은 검색 결과에서 저장 (추가 호출 없음)
        meta[key] = {
            "productId": match.get("productId"),
            "itemId": item_id(match),
            "productName": match.get("productName"),
            "image": match.get("productImage"),
            "rocket": bool(match.get("isRocket")),
            "freeShipping": bool(match.get("isFreeShipping")),
            # 검색 결과의 상품 링크는 내 파트너스 계정의 제휴링크라서 그대로 저장
            "link": match.get("productUrl"),
        }
        print(f"  ✅ {price:,}원 (상품 {match.get('productId')} / 옵션 {item_id(match)}) {match.get('productName')}")

    with open("data/prices.json", "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("\n저장 완료!")


if __name__ == "__main__":
    main()
