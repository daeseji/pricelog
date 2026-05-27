import os, json, hmac, hashlib, datetime, requests, urllib.parse

ACCESS_KEY = os.environ["COUPANG_ACCESS_KEY"]
SECRET_KEY = os.environ["COUPANG_SECRET_KEY"]
BASE_URL = "https://api-gateway.coupang.com"
PATH = "/v2/providers/affiliate_open_api/apis/openapi/products/search"

def try_request(fmt_name, canonical, full_url, datetime_str):
    sig = hmac.new(SECRET_KEY.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    headers = {
        "Authorization": f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, signed-date={datetime_str}, signature={sig}",
        "Content-Type": "application/json;charset=UTF-8",
    }
    r = requests.get(full_url, headers=headers, timeout=10)
    print(f"[{fmt_name}] {r.status_code}: {r.text[:80]}")
    return r.status_code == 200, r

def main():
    keyword = "코카콜라"
    params = {"keyword": keyword, "limit": "20"}
    dt = datetime.datetime.utcnow().strftime("%y%m%dT%H%M%SZ")

    sorted_items = sorted(params.items())
    qs_plus   = urllib.parse.urlencode(sorted_items)
    qs_quote  = urllib.parse.urlencode(sorted_items, quote_via=urllib.parse.quote)
    qs_plus_u = urllib.parse.urlencode(params)
    qs_quote_u= urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

    formats = [
        ("sorted_plus_noQ",  dt+"GET"+PATH+qs_plus,    BASE_URL+PATH+"?"+qs_plus),
        ("sorted_plus_Q",    dt+"GET"+PATH+"?"+qs_plus, BASE_URL+PATH+"?"+qs_plus),
        ("sorted_quote_noQ", dt+"GET"+PATH+qs_quote,   BASE_URL+PATH+"?"+qs_quote),
        ("sorted_quote_Q",   dt+"GET"+PATH+"?"+qs_quote,BASE_URL+PATH+"?"+qs_quote),
        ("unsrt_plus_noQ",   dt+"GET"+PATH+qs_plus_u,  BASE_URL+PATH+"?"+qs_plus_u),
        ("unsrt_plus_Q",     dt+"GET"+PATH+"?"+qs_plus_u,BASE_URL+PATH+"?"+qs_plus_u),
        ("unsrt_quote_noQ",  dt+"GET"+PATH+qs_quote_u, BASE_URL+PATH+"?"+qs_quote_u),
        ("unsrt_quote_Q",    dt+"GET"+PATH+"?"+qs_quote_u,BASE_URL+PATH+"?"+qs_quote_u),
    ]

    for name, canonical, url in formats:
        ok, r = try_request(name, canonical, url, dt)
        if ok:
            print(f"\n✅ 성공한 형식: {name}")
            break

    with open("data/prices.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    with open("data/prices.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
