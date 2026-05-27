import json, hmac, hashlib, datetime, requests, urllib.parse

ACCESS_KEY = __import__('os').environ["COUPANG_ACCESS_KEY"]
SECRET_KEY = __import__('os').environ["COUPANG_SECRET_KEY"]
BASE_URL = "https://api-gateway.coupang.com"
PATH = "/v2/providers/affiliate_open_api/apis/openapi/products/search"

def try_all(keyword):
    dt = datetime.datetime.utcnow().strftime("%y%m%dT%H%M%SZ")
    params = sorted({"keyword": keyword, "limit": "20"}.items())
    
    qs_encoded = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    qs_plus    = urllib.parse.urlencode(params)
    qs_raw     = "&".join(f"{k}={v}" for k, v in params)  # 한글 그대로
    url = BASE_URL + PATH + "?" + qs_encoded

    combos = [
        ("raw_Q",     "GET", PATH + "?" + qs_raw),
        ("raw_noQ",   "GET", PATH + qs_raw),
        ("enc_Q",     "GET", PATH + "?" + qs_encoded),
        ("plus_Q",    "GET", PATH + "?" + qs_plus),
        ("noParam",   "GET", PATH),
    ]
    for name, method, canonical_tail in combos:
        canonical = dt + method + canonical_tail
        sig = hmac.new(SECRET_KEY.encode(), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        auth = f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, signed-date={dt}, signature={sig}"
        r = requests.get(url, headers={"Authorization": auth, "Content-Type": "application/json;charset=UTF-8"}, timeout=10)
        print(f"[{name}] {r.status_code}: {r.text[:60]}")
        if r.status_code == 200:
            return r.json().get("data", {}).get("productData", [{}])[0].get("productPrice")
    return None

def main():
    with open("data/prices.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    for product in data["products"]:
        print(f"\n조회 중: {product['name']}")
        price = try_all(product["keyword"])
        if price:
            product["history"].append({"date": now, "price": price})
            product["history"] = product["history"][-180:]
            print(f"✅ {price:,}원")
        else:
            print("❌ 실패")
    with open("data/prices.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("\n저장 완료!")

if __name__ == "__main__":
    main()
