"""상품 사진을 저장소(img/)에 받아 둬요.

쿠팡 파트너스 이미지 주소(ads-partners.coupang.com)는 광고 차단기가 막아서
사진이 안 보일 수 있어요. 가격 기록에 저장된 사진 주소에서 한 번만 받아 두고,
사이트는 저장소 안의 사진을 보여줘요.

쿠팡 파트너스 API는 부르지 않아요. (이미 저장된 사진 주소만 내려받아요)
"""
import io, json, os, re, time
import requests

try:
    from PIL import Image
except ImportError:  # Pillow가 없으면 받은 그대로 저장해요
    Image = None

PRICES = "data/prices.json"
IMG_DIR = "img"
MAX_SIDE = 480
MAX_BYTES = 120_000
TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}


def main():
    with open(PRICES, encoding="utf-8") as f:
        prices = json.load(f)
    os.makedirs(IMG_DIR, exist_ok=True)
    changed = False

    for name, m in prices.get("meta", {}).items():
        url, key = m.get("image"), str(m.get("itemId") or m.get("productId") or "")
        if not url or not re.fullmatch(r"\d+", key):
            continue
        local = m.get("localImage")
        if local and local.startswith(f"{IMG_DIR}/{key}.") and os.path.exists(local) and (Image is None or os.path.getsize(local) <= MAX_BYTES):
            continue
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (pricelog image cache)"})
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"  ❌ {name}: 사진을 받지 못했어요 ({e})")
            continue
        ext = TYPES.get(r.headers.get("Content-Type", "").split(";")[0].strip())
        if not ext or len(r.content) < 500:
            print(f"  ❌ {name}: 사진 형식이 아니에요 ({r.headers.get('Content-Type')})")
            continue
        data = r.content
        if Image is not None:
            # 가로세로 480px 이하 JPEG로 줄여서 페이지를 가볍게 해요
            img = Image.open(io.BytesIO(data)).convert("RGB")
            img.thumbnail((MAX_SIDE, MAX_SIDE))
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
            data, ext = buf.getvalue(), "jpg"
        path = f"{IMG_DIR}/{key}.{ext}"
        if local and local != path and os.path.exists(local):
            os.remove(local)
        with open(path, "wb") as f:
            f.write(data)
        m["localImage"] = path
        changed = True
        print(f"  ✅ {name}: {path} ({len(data) // 1024}KB)")
        time.sleep(1)

    if changed:
        with open(PRICES, "w", encoding="utf-8") as f:
            json.dump(prices, f, ensure_ascii=False, indent=2)
            f.write("\n")
    print("사진 저장 완료!")


if __name__ == "__main__":
    main()
