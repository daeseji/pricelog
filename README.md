# 싸다구 🏷️

쌀 때 사다구. 자주 사는 쿠팡 상품의 가격을 매일 한 번 기록하는 개인용 가격 추적 페이지.

사이트: https://daeseji.github.io/pricelog/

- `data/products.json` — 추적할 상품 목록 (직접 수정)
- `data/prices.json` — 매일 자동으로 쌓이는 가격 기록과 상품 사진 (수정하지 않기)
- `update_prices.py` — GitHub Actions가 매일 오전 9시쯤 실행

## 상품 추가하기

`data/products.json`의 `products`에 아래처럼 한 묶음을 추가합니다.

```json
{
  "name": "화면에 보일 깔끔한 이름 (예: 라운드랩 독도 토너)",
  "title": "쿠팡 상품명 그대로 (예: 라운드랩 독도 토너, 500ml, 1개)",
  "category": "먹거리 / 음료 / 뷰티·건강 / 반려견 등",
  "id": "",
  "url": "쿠팡 상품 주소 (제휴링크가 없을 때만 사용)",
  "link_b64": "제휴링크를 Base64로 바꾼 값"
}
```

- `title`로 쿠팡을 검색해서 **상품명이 정확히 같은 상품**만 기록합니다. 한 번 찾으면 상품 ID를 기억해서 다음부터는 ID로 찾습니다.
- `id`를 직접 넣으면(쿠팡 주소 `/vp/products/숫자`의 숫자) 그 ID로만 찾습니다.
- 기록이 안 되면 Actions 실행 기록에 검색 결과 상품 목록이 표시되니, 그걸 보고 `title`이나 `id`를 맞추면 됩니다.
- 상품 사진은 같은 검색 결과에서 함께 저장됩니다. (추가 호출 없음)
- 가격 기록은 `name` 기준으로 저장되므로, `name`을 바꾸면 기록이 새로 시작됩니다.

## 제휴링크 (Base64)

1. 쿠팡 파트너스 사이트에서 상품 링크를 만듭니다. (예: `https://link.coupang.com/a/g6Z7ZtzVim`)
2. Base64로 바꿉니다. (예: `aHR0cHM6Ly9saW5rLmNvdXBhbmcuY29tL2EvZzZaN1p0elZpbQ`)
3. `link_b64`에 넣으면 버튼이 `go.html?u=...`로 연결되어 쿠팡으로 이동합니다.

## 쿠팡 파트너스 API 안전장치

- 하루 한 번만 실행, 상품 1개당 API 1회 호출
- 호출 사이 400초 대기 → 1시간에 최대 9회
- 한 번에 최대 15개 상품까지만 조회
- 오류가 나면 재시도 없이 바로 중단

이전 기록(다른 상품 가격이 섞였던 데이터)은 `data/old_prices_backup.json`에 보관했습니다.
