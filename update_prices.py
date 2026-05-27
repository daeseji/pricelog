import json, hmac, hashlib, requests, urllib.parse, os
from time import gmtime, strftime

ACCESS_KEY = os.environ["COUPANG_ACCESS_KEY"]
SECRET_KEY = os.environ["COUPANG_SECRET_KEY"]
DOMAIN = "https://api-gateway.coupang.com"

def generateHmac(method, url, secretKey, accessKey):
    path, *query = url.split("?")
    datetimeGMT = strftime('%y%m%d', gmtime()) + 'T' + strftime('%H%M%S', gmtime()) + 'Z'
    message = datetimeGMT + method + path + (query[0] if query else "")
    signature = hmac.new(bytes(secretKey, "utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return "CEA algorithm=HmacSHA256, access-key={}, signed-date={}, signature={}".format(accessKey, datetimeGMT, signature)

def get_price(keyword, product_id):
    # v1 경로 먼저 시도, 안되면 기존 경로
    for path in [
        "/v2/providers/affiliate_open_api/apis/openapi/v1/products/search",
        "/v2/providers/affiliate_open_api/apis/openapi/products/search",
    ]:
        qs = urllib.parse.urlencode({"keyword": keyword, "limit": "20"}, quote_via=urllib.parse.quote)
        url = path + "?" + qs
        auth = generateHmac("GET", url, SECRET_KEY, ACCESS_KEY)
        r = requests.get(DOMAIN + url, headers={"Authorization": auth, "Content-Type": "application/json"}, timeout=10)
        print(f"  [{path[-20:]}] {r.status_code}: {r.text[:80]}")
        if r.status_code == 200:
            products = r.json().get("data", {}).get("productData", [])
            for p in products:
                if str(p.get("productId")) == str(product_id):
                    return p.get("productPrice")
            return products[0].get("productPrice") if products else None
    return None

def main():
    with open("data/prices.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    import datetime
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    for product in data["products"]:
        print(f"\n조회 중: {product['name']}")
        price = get_price(product["keyword"], product["id"])
        if price:
            product["history"].append({"date": now, "price": price})
            product["history"] = product["history"][-180:]
            print(f"  ✅ {price:,}원")
        else:
            print(f"  ❌ 실패")
    with open("data/prices.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("\n저장 완료!")

if __name__ == "__main__":
    main()
