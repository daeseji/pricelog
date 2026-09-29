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
MAX_CALLS_PER_RUN = 15
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
    return re.sub(r"[\s,.\-_/()\[\]]", "", str(name)).lower()


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


def find_product(product, results):
    # 정확히 같은 상품일 때만 가격을 기록합니다. (비슷한 다른 상품 가격이 섞이는 문제 방지)
    # 1) 상품 ID가 있으면 ID로 비교, 2) 없으면 상품명이 완전히 같은지 비교
    if product.get("id"):
        for p in results:
            if str(p.get("productId")) == str(product["id"]):
                return p
        return None
    target = normalize(product["name"])
    for p in results:
        if normalize(p.get("productName", "")) == target:
            return p
    return None


def main():
    with open("data/products.json", "r", encoding="utf-8") as f:
        products = json.load(f)["products"]
    with open("data/prices.json", "r", encoding="utf-8") as f:
        prices = json.load(f)
    history = prices.setdefault("history", {})

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")

    if len(products) > MAX_CALLS_PER_RUN:
        print(f"⚠️ 상품이 {len(products)}개예요. 안전을 위해 앞의 {MAX_CALLS_PER_RUN}개만 조회합니다.")
        products = products[:MAX_CALLS_PER_RUN]

    for i, product in enumerate(products):
        if i > 0:
            time.sleep(DELAY_SECONDS)
        print(f"\n조회 중 ({i + 1}/{len(products)}): {product['name']}")
        try:
            results = search(product["keyword"])
        except ApiError as e:
            print(f"  ⛔ API 오류로 여기서 멈춥니다 (재시도 안 함): {e}")
            break

        match = find_product(product, results)
        if match is None:
            print("  ❌ 검색 결과에서 같은 상품을 못 찾아서 기록하지 않았어요. 검색 결과 상위 상품:")
            for p in results[:5]:
                print(f"     - [{p.get('productId')}] {p.get('productName')} / {p.get('productPrice')}원")
            continue

        price = match.get("productPrice")
        if not price:
            print("  ❌ 가격 정보가 없어서 기록하지 않았어요.")
            continue
        entries = history.setdefault(product["name"], [])
        entries.append({"date": now, "price": price})
        history[product["name"]] = entries[-HISTORY_LIMIT:]
        print(f"  ✅ {price:,}원 (상품 ID {match.get('productId')})")

    with open("data/prices.json", "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("\n저장 완료!")


if __name__ == "__main__":
    main()
