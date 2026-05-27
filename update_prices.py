import os
import json
import hmac
import hashlib
import datetime
import requests
import urllib.parse

ACCESS_KEY = os.environ["COUPANG_ACCESS_KEY"]
SECRET_KEY = os.environ["COUPANG_SECRET_KEY"]
BASE_URL = "https://api-gateway.coupang.com"


def get_headers(method, path, params=None):
    datetime_str = datetime.datetime.utcnow().strftime("%y%m%dT%H%M%SZ")

    if params:
        sorted_items = sorted(params.items())
        query_string = urllib.parse.urlencode(sorted_items, quote_via=urllib.parse.quote)
        canonical = datetime_str + method + path + "?" + query_string
        full_url = BASE_URL + path + "?" + query_string
    else:
        canonical = datetime_str + method + path
        full_url = BASE_URL + path

    # ← 여기가 핵심 변경점: hex 디코딩
    key = bytes.fromhex(SECRET_KEY)

    signature = hmac.new(
        key,
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "Authorization": (
            f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, "
            f"signed-date={datetime_str}, signature={signature}"
        ),
        "Content-Type": "application/json;charset=UTF-8",
    }
    return headers, full_url


def get_price(keyword, product_id):
    path = "/v2/providers/affiliate_open_api/apis/openapi/products/search"
    params = {"keyword": keyword, "limit": "20"}

    headers, full_url = get_headers("GET", path, params)
    resp = requests.get(full_url, headers=headers, timeout=10)

    if resp.status_code != 200:
        print(f"  API 오류 {resp.status_code}: {resp.text[:300]}")
        return None

    data = resp.json()
    products = data.get("data", {}).get("productData", [])

    for p in products:
        if str(p.get("productId")) == str(product_id):
            price = p.get("productPrice")
            print(f"  ID 매칭: {price}원")
            return price

    if products:
        price = products[0].get("productPrice")
        print(f"  첫번째 결과: {price}원")
        return price

    print("  검색 결과 없음")
    return None


def main():
    with open("data/prices.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    now = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    ).strftime("%Y-%m-%d %H:%M")

    for product in data["products"]:
        print(f"조회 중: {product['name']}")
        price = get_price(product["keyword"], product["id"])
        if price is not None:
            product["history"].append({"date": now, "price": price})
            product["history"] = product["history"][-180:]
            print(f"  ✅ {price:,}원\n")
        else:
            print(f"  ❌ 실패\n")

    with open("data/prices.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("저장 완료!")


if __name__ == "__main__":
    main()
