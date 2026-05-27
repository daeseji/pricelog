import json, hmac, hashlib, datetime, requests, urllib.parse, os

ACCESS_KEY = os.environ["COUPANG_ACCESS_KEY"]
SECRET_KEY = os.environ["COUPANG_SECRET_KEY"]
BASE_URL = "https://api-gateway.coupang.com"
PATH = "/v2/providers/affiliate_open_api/apis/openapi/products/search"

def try_all(keyword):
    dt = datetime.datetime.utcnow().strftime("%y%m%dT%H%M%SZ")
    params = sorted({"keyword": keyword, "limit": "20"}.items())
    qs_enc = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    qs_raw = "&".join(f"{k}={v}" for k, v in params)
    url = BASE_URL + PATH + "?" + qs_enc

    key_str = SECRET_KEY.encode("utf-8")
    key_hex = bytes.fromhex(SECRET_KEY)

    combos = [
        ("str_enc_Q",  key_str, dt + "GET" + PATH + "?" + qs_enc),
        ("str_raw_Q",  key_str, dt + "GET" + PATH + "?" + qs_raw),
        ("str_noParam",key_str, dt + "GET" + PATH),
        ("hex_enc_Q",  key_hex, dt + "GET" + PATH + "?" + qs_enc),
        ("hex_raw_Q",  key_hex, dt + "GET" + PATH + "?" + qs_raw),
        ("hex_noParam",key_hex, dt + "GET" + PATH),
    ]
    for name, key, canonical in combos:
        sig = hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        auth = f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, signed-date={dt}, signature={sig}"
        r = requests.get(url, headers={"Authorization": auth, "Content-Type": "application/json;charset=UTF-8"}, timeout=10)
        print(f"[{name}] {r.status_code}: {r.text[:60]}")
        if r.status_code == 200:
            data = r.json().get("data", {}).get("productData", [])
            return data[0].get("productPrice") if data else None
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
