# 싸다구 제휴 링크 서버

'내 상품'에 담긴 쿠팡 상품을 방문자가 **직접 눌렀을 때만** 싸다구의 쿠팡 파트너스 제휴 링크로 바꿔 주는 작은 서버예요. Cloudflare Workers 무료 플랜에서 돌아가요.

## 왜 Vercel이 아니라 Cloudflare인가요

Vercel 무료(Hobby) 플랜은 비상업적 개인 용도로만 쓸 수 있고, 제휴 링크가 주목적인 사이트도 상업적 이용으로 봐요. 이 서버는 하는 일이 제휴 링크 생성뿐이라 Cloudflare Workers 무료 플랜에 두었어요.

## 설정

1. Cloudflare 대시보드 > Workers & Pages > Create > Worker로 `sadagu-link`를 만들고, `link.js` 내용을 그대로 붙여 넣어 배포해요.
2. Settings > Variables and Secrets에 비밀값 두 개를 넣어요. 쿠팡 파트너스 > 추가 기능 > 파트너스 API 화면에 있는 값이에요.
   - `COUPANG_ACCESS_KEY`
   - `COUPANG_SECRET_KEY`
3. (선택) Storage > KV에서 네임스페이스를 만들고 Worker에 `LINKS`라는 이름으로 연결하면, 한 번 만든 링크를 오래 저장해 API 호출을 줄여요.
4. 배포된 주소(`https://sadagu-link.<계정>.workers.dev`)를 `assets/mine.js`의 `LINK_API`에 넣고 `python3 scripts/build_site.py`로 페이지를 다시 만들어요.

## 지키는 것

- 방문자가 버튼을 누른 순간에만 호출하고, 쿠팡을 자동으로 열거나 숨은 창을 띄우지 않아요.
- `https://daeseji.github.io`에서 온 요청만 받아요(브라우저 기준). IP당 시간당 30회까지만 새로 만들어요.
- 쿠팡 상품 주소(`/vp/products/...`)와 쿠팡 앱 공유 링크만 받고, 광고·추적 파라미터는 버려요.
