import json, hmac, hashlib, datetime, requests, urllib.parse

ACCESS_KEY = __import__('os').environ["COUPANG_ACCESS_KEY"]
SECRET_KEY = __import__('os').environ["COUPANG_SECRET_KEY"]
BASE_URL = "https://api-gateway.coupang.com"
PATH = "/v2/providers/affiliate_open_api/apis/openapi/products/search"

def try_all(keyword):
    dt = datetime.datetime.utcnow().strftime("%y%m%dT%H%M%SZ")
    params = {"keyword": keyword, "limit": "20"}
    si = sorted(params.items())
    qs = urllib.parse.urlencode(si, quote_via=urllib.parse.quote)
    url = BASE_URL + PATH + "?" + qs

    combos = [
        ("GET",  f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, signed-date={dt}, signature="),
        ("GET",  f"CEA algorithm=HmacSHA256,access-key={ACCESS_KEY},signed-date={dt},signature="),
        ("get",  f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, signed-date={dt}, signature="),
        ("get",  f"CEA algorithm=HmacSHA256,access-key={ACCESS_KEY},signed-date={dt},signature="),
    ]

    for method, auth_prefix in combos:
        canonical = dt + method + PATH + "?" + qs
        sig = hmac.new(SECRET_KEY.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        headers = {
            "Authorization": auth_prefix + sig,
            "Content-Type": "application/json;charset=UTF-8",
        }
        r = requests.get(url, headers=headers, timeout=10)
        name = f"method={method}, spaces={'Y' if ', ' in auth_prefix else 'N'}"
        print(f"[{name}] {r.status_code}: {r.text[:60]}")
        if r.status_code == 200:
            return r.json().get("data", {}).get("productData", [{}])[0].get("productPrice")
    return None

def main():
    import os
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
