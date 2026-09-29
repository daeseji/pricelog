// 장보기 노트마다 공유 이미지(1200×630)를 만듭니다.
// 먼저 python3 scripts/build_site.py 로 og/manifest.json 을 만든 뒤 실행하세요.
//
//   npm i -D playwright && npx playwright install chromium   (처음 한 번)
//   node scripts/make_og.cjs                  # 새로 생긴 글만
//   node scripts/make_og.cjs --all            # 전부 다시
//   node scripts/make_og.cjs --font ./PretendardVariable.woff2   # 글꼴 파일 직접 지정
const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'og', 'tips');
const args = process.argv.slice(2);
const all = args.includes('--all');
const fontArg = args.includes('--font') ? args[args.indexOf('--font') + 1] : null;
const FONT_CSS = 'https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css';

const COLORS = {
  shop: { bg: '#FFE27A', ink: '#1B1600', chip: '#17171B', icon: '#8A6A00' },
  fresh: { bg: '#BFEBCF', ink: '#0B2A17', chip: '#0F8A43', icon: '#0F8A43' },
  kitchen: { bg: '#CCDCFF', ink: '#0B1A3F', chip: '#1D4ED8', icon: '#1D4ED8' },
  recipe: { bg: '#FFD0B5', ink: '#3A1403', chip: '#D9480F', icon: '#D9480F' },
  home: { bg: '#DDCCFF', ink: '#1F0B45', chip: '#6D28D9', icon: '#6D28D9' },
};

const MARK = `<svg viewBox="0 0 64 64" width="56" height="56"><rect width="64" height="64" rx="16" fill="#FFD84D"/><g transform="rotate(-14 32 32)"><path d="M15 19h24.5a3 3 0 0 1 2.1.9l11.9 11.9a1.7 1.7 0 0 1 0 2.4L41.6 45.1a3 3 0 0 1-2.1.9H15a4 4 0 0 1-4-4V23a4 4 0 0 1 4-4Z" fill="#17171B"/><circle cx="44.5" cy="32.5" r="3" fill="#FFD84D"/><circle cx="20.5" cy="29" r="2.7" fill="#FFD84D"/><circle cx="31" cy="29" r="2.7" fill="#FFD84D"/><path d="M19.5 35.5c3.6 3.8 9.4 3.8 13 0" fill="none" stroke="#FFD84D" stroke-width="3" stroke-linecap="round"/></g></svg>`;

const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function card(n) {
  const c = COLORS[n.cat] || COLORS.shop;
  const fontFace = fontArg
    ? `@font-face{font-family:"Pretendard Variable";font-weight:45 920;src:url("data:font/woff2;base64,${fs.readFileSync(fontArg).toString('base64')}") format("woff2");}`
    : '';
  return `<!DOCTYPE html><html><head><meta charset="utf-8">${fontArg ? '' : `<link rel="stylesheet" href="${FONT_CSS}">`}
<style>${fontFace}
*{box-sizing:border-box}html,body{margin:0}
body{width:1200px;height:630px;background:${c.bg};color:${c.ink};font-family:"Pretendard Variable",Pretendard,sans-serif;letter-spacing:-0.04em;position:relative;overflow:hidden;word-break:keep-all}
.brand{position:absolute;left:80px;top:72px;display:flex;align-items:center;gap:16px;font-size:30px;font-weight:800}
.brand span{font-weight:600;opacity:.6}
.chip{position:absolute;left:80px;top:178px;background:${c.chip};color:#fff;font-size:26px;font-weight:800;padding:10px 20px;border-radius:14px;letter-spacing:-0.02em}
h1{position:absolute;left:80px;top:250px;width:760px;margin:0;font-size:64px;line-height:1.22;font-weight:850;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.url{position:absolute;left:80px;bottom:64px;font-size:24px;font-weight:600;opacity:.55;letter-spacing:-0.01em}
.icon{position:absolute;right:70px;top:170px;width:300px;height:300px;color:${c.icon};opacity:.9}
.icon svg{width:100%;height:100%}
</style></head><body>
<div class="brand">${MARK}싸다구 <span>장보기 노트</span></div>
<div class="chip">${esc(n.category)}</div>
<h1>${esc(n.title)}</h1>
<div class="url">daeseji.github.io/pricelog</div>
<div class="icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">${n.icon}</svg></div>
</body></html>`;
}

(async () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'og', 'manifest.json'), 'utf8'));
  fs.mkdirSync(OUT, { recursive: true });
  const todo = manifest.filter(n => all || !fs.existsSync(path.join(OUT, `${n.slug}.png`)));
  if (!todo.length) { console.log('새로 만들 공유 이미지가 없어요'); return; }
  const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });
  for (const n of todo) {
    await page.setContent(card(n), { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: path.join(OUT, `${n.slug}.png`) });
    console.log('  ✓', n.slug);
  }
  await browser.close();
  console.log(`공유 이미지 ${todo.length}장을 만들었어요`);
})();
