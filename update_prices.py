import os
import json
import datetime
import requests
from bs4 import BeautifulSoup

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

def get_price(url):
    try:
        resp = requests.get(url, headers=BASE_HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        # 가격 셀렉터 시도
        selectors = [
            "span.total-price strong",
            "span.price-value",
            ".prod-sale-price .price-value",
            "#prod-sale-price .price-value",
        ]
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                price_str = el.get_text().strip().replace(",", "").replace("원", "")
                return int(price_str)
    except Exception as e:
        print(f"  오류: {e}")
    return None


def main():
    with open("data/prices.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    now = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    ).strftime("%Y-%m-%d %H:%M")

    for product in data["products"]:
        print(f"조회 중: {product['name']}")
        price = get_price(product["url"])

        if price:
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
