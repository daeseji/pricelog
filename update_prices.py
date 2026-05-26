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
        query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        full_path = path + "?" + query_string
    else:
        full_path = path

    message = datetime_str + "\n" + method + "\n" + full_path + "\n"

    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return {
        "Authorization": (
            f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, "
            f"signed-date={datetime_str}, signature={signature}"
        ),
        "Content-Type": "application/json",
    }


def get_price(keyword, product_id):
    path = "/v2/providers/affiliate_open_api/apis/openapi/products/search"
    params = {"keyword": keyword, "limit": "20"}

    headers = get_headers("GET", path, params)
    resp = requests.get(BASE_URL + path, params=params, headers=headers, timeout=10)

    if resp.status_code != 200:
        print(f"  API 오류 {resp.status_code}: {resp.text[:200]}")
        return None

    data = resp.json()
    products = data.get("data", {}).get("productData", [])

    # productId 일치하는 상품 먼저 찾기
    for p in products:
        if str(p.get("productId")) == str(product_id):
            price = p.get("productPrice")
            print(f"  ID 매칭 성공: {price}원")
            return price

    # 없으면 첫 번째 결과 사용
    if products:
        price = products[0].get("productPrice")
        print(f"  첫 번째 결과 사용: {price}원")
        return price

    return None


def main():
    with open("data/prices.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime(
        "%Y-%m-%d %H:%M"
    )

    for product in data["products"]:
        print(f"조회 중: {product['name']}")
        price = get_price(product["keyword"], product["id"])

        if price is not None:
            product["history"].append({"date": now, "price": price})
            # 최근 180개만 유지 (하루 2회 × 90일)
            product["history"] = product["history"][-180:]
            print(f"  ✅ 완료: {price:,}원\n")
        else:
            print(f"  ❌ 가격 조회 실패\n")

    with open("data/prices.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("저장 완료!")


if __name__ == "__main__":
    main()
