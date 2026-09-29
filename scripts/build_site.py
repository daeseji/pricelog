#!/usr/bin/env python3
"""싸다구 페이지 생성기

content/tips/*.md (장보기 노트)와 content/links.json (링크 모음)으로
tips/, links/, about/, 404.html, sitemap.xml을 만들고,
index.html의 메뉴(머리말)와 꼬리말을 다른 페이지와 똑같이 맞춥니다.

    pip install markdown
    python3 scripts/build_site.py
"""
import html
import json
import math
import pathlib
import re

import markdown
from markdown.extensions.toc import slugify_unicode

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE_URL = "https://daeseji.github.io/pricelog/"
SITE_BASE = "/pricelog/"  # 404 페이지처럼 주소가 정해지지 않은 곳에서 쓰는 절대 경로
FONT_CSS = "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
DATA_REMOTE = "https://raw.githubusercontent.com/daeseji/pricelog/main/data"

CATS = {"쇼핑 팁": "shop", "재료 고르기": "fresh", "보관·요리": "kitchen"}

# 노트 표지 아이콘 (24×24 선 아이콘, meat는 Lucide 아이콘 · ISC 라이선스)
# SNS 로고는 Simple Icons (CC0) · content/brand-icons.json
NOTE_ICONS = {
    "tag": '<path d="M3.5 12.6V4.8a1.3 1.3 0 0 1 1.3-1.3h7.8l8 8a1.3 1.3 0 0 1 0 1.9l-6.9 6.9a1.3 1.3 0 0 1-1.9 0l-8-8Z"/><circle cx="8.3" cy="8.3" r="1.4"/>',
    "scale": '<path d="M12 4v16M7 20h10M5 7h14"/><path d="M8 7 5 13.5a3 3 0 0 0 6 0L8 7ZM16 7l-3 6.5a3 3 0 0 0 6 0L16 7Z"/>',
    "box": '<path d="M3.5 7.5 12 3l8.5 4.5v9L12 21l-8.5-4.5v-9Z"/><path d="M3.5 7.5 12 12l8.5-4.5M12 12v9M7.8 5.3l8.5 4.5"/>',
    "leaf": '<path d="M5 19c0-8.3 5.2-14 14-14 0 8.8-5.7 14-14 14Z"/><path d="M5 19 13.5 10.5"/>',
    "fish": '<path d="M6.5 12c2.6-3.6 5.7-5.5 9-5.5 2.8 0 5 2.2 6 5.5-1 3.3-3.2 5.5-6 5.5-3.3 0-6.4-1.9-9-5.5Z"/><path d="M6.5 12 2.5 8v8l4-4Z"/><circle cx="16.8" cy="11" r=".9"/>',
    "meat": '<circle cx="12.5" cy="8.5" r="2.5"/><path d="M12.5 2a6.5 6.5 0 0 0-6.22 4.6c-1.1 3.13-.78 3.9-3.18 6.08A3 3 0 0 0 5 18c4 0 8.4-1.8 11.4-4.3A6.5 6.5 0 0 0 12.5 2Z"/><path d="m18.5 6 2.19 4.5a6.48 6.48 0 0 1 .31 2 6.49 6.49 0 0 1-2.6 5.2C15.4 20.2 11 22 7 22a3 3 0 0 1-2.68-1.66L2.4 16.5"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4M7.5 14h2M11 14h2M14.5 14h2M7.5 17h2M11 17h2"/>',
    "snow": '<path d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9"/><path d="m9.5 4.5 2.5 2 2.5-2M9.5 19.5l2.5-2 2.5 2M4 10.6l3.1.4-.6 3M20 13.4l-3.1-.4.6-3M4.6 13.6l2.9-.9.9 3M19.4 10.4l-2.9.9-.9-3"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "pot": '<path d="M4 10h16v5.5a4.5 4.5 0 0 1-4.5 4.5h-7A4.5 4.5 0 0 1 4 15.5V10Z"/><path d="M2.5 10h19M9 6.8c0-1 1-1.4 1-2.4M14 6.8c0-1 1-1.4 1-2.4"/>',
}

# 상품 카테고리 아이콘 (index.html과 같은 모양)
PRODUCT_ICONS = {
    "먹거리": '<path d="M3.5 11.5h17a8.5 8.5 0 0 1-17 0Z"/><path d="M8.5 8c0-1.2 1.2-1.6 1.2-2.8M12.5 8c0-1.2 1.2-1.6 1.2-2.8M16.5 8c0-1.2 1.2-1.6 1.2-2.8"/>',
    "음료": '<path d="M6.5 8h11l-1.3 12a1.2 1.2 0 0 1-1.2 1H9a1.2 1.2 0 0 1-1.2-1L6.5 8Z"/><path d="M5.5 8h13M12.5 8l1.6-5H17"/>',
    "뷰티·건강": '<path d="M12 3.2s6 6.4 6 10.8a6 6 0 0 1-12 0c0-4.4 6-10.8 6-10.8Z"/><path d="M9.3 14.5a2.8 2.8 0 0 0 2.2 2.6"/>',
    "반려견": '<circle cx="6.3" cy="10.3" r="1.7"/><circle cx="9.8" cy="6.6" r="1.7"/><circle cx="14.2" cy="6.6" r="1.7"/><circle cx="17.7" cy="10.3" r="1.7"/><path d="M12 11.3c-2.9 0-5.4 3.1-5.4 5.4 0 1.5 1.2 2.3 2.7 2.3 1.1 0 1.7-.5 2.7-.5s1.6.5 2.7.5c1.5 0 2.7-.8 2.7-2.3 0-2.3-2.5-5.4-5.4-5.4Z"/>',
    "생활용품": '<path d="M9.5 3h4v3h-4z"/><path d="M8 6h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2Z"/><path d="M17 9.5h1a1.5 1.5 0 0 1 1.5 1.5v2.5M9 12h5"/>',
    "_": '<path d="M3.5 12.6V4.8a1.3 1.3 0 0 1 1.3-1.3h7.8l8 8a1.3 1.3 0 0 1 0 1.9l-6.9 6.9a1.3 1.3 0 0 1-1.9 0l-8-8Z"/><circle cx="8.3" cy="8.3" r="1.4"/>',
}

CALLOUTS = {"팁": "tip", "주의": "warn", "한 줄 요약": "sum", "공식": "sum", "참고": "note"}
PARTNER_COLORS = ["#2F6FEB", "#0E9F6E", "#E8590C", "#7048E8", "#C2255C", "#1098AD", "#5C940D", "#D6336C", "#364FC7", "#AE3EC9", "#F08C00"]


def esc(s):
    return html.escape(str(s), quote=True)


def svg(paths, cls=""):
    c = f' class="{cls}"' if cls else ""
    return f'<svg{c} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths}</svg>'


def brand_svg(path):
    return f'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="{path}"/></svg>'


def korean_date(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{y}년 {m}월 {d}일"


# ---------- 콘텐츠 읽기 ----------

def parse_note(path):
    text = path.read_text(encoding="utf-8")
    _, fm, body = text.split("---", 2)
    meta = {}
    for line in fm.strip().splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    meta["slug"] = path.stem
    meta["order"] = int(meta.get("order", 99))
    meta["related"] = [x.strip() for x in meta.get("related", "").split(",") if x.strip()]
    meta["cat"] = CATS.get(meta["category"], "shop")

    md = markdown.Markdown(
        extensions=["tables", "toc", "sane_lists"],
        extension_configs={"toc": {"slugify": slugify_unicode, "toc_depth": "2"}},
    )
    out = md.convert(body)

    def callout(m):
        label = m.group(1)
        cls = CALLOUTS.get(label, "")
        return f'<blockquote class="{cls}">\n<p><strong class="co">{label}</strong>' if cls else m.group(0)

    out = re.sub(r"<blockquote>\s*<p><strong>(.+?)</strong>", callout, out)
    out = out.replace("<li>[ ] ", '<li class="check">')
    out = out.replace("<table>", '<div class="table-scroll"><table>').replace("</table>", "</table></div>")
    meta["html"] = out
    meta["toc"] = [t for t in _flatten(md.toc_tokens) if t["level"] == 2]
    chars = len(re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", out)))
    meta["read"] = max(1, math.ceil(chars / 500))
    return meta


def _flatten(tokens):
    for t in tokens:
        yield t
        yield from _flatten(t.get("children", []))


# ---------- 공통 조각 ----------

def page_head(title, desc, path, root, extra=""):
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE_URL}{path}">
<meta name="theme-color" content="#F6F5F0" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#111113" media="(prefers-color-scheme: dark)">
<meta property="og:type" content="website">
<meta property="og:site_name" content="싸다구">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{SITE_URL}{path}">
<meta property="og:image" content="{SITE_URL}og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
<link rel="icon" href="{root}favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{root}apple-touch-icon.png">
<link rel="stylesheet" href="{FONT_CSS}">
<link rel="stylesheet" href="{root}assets/site.css">
{extra}</head>
<body>
"""


def header(root, active):
    items = [
        ("home", "", "가격"),
        ("tips", "tips/", '<span class="lg">장보기 </span>노트'),
        ("about", "about/", "소개"),
        ("links", "links/", "링크"),
    ]
    nav = "".join(
        f'<a href="{(root + href) or "./"}"{" aria-current=" + chr(34) + "page" + chr(34) if key == active else ""}>{label}</a>'
        for key, href, label in items
    )
    home = root or "./"
    return f"""<header class="top" id="top">
  <div class="wrap top-row">
    <a class="logo" href="{home}" aria-label="싸다구 홈"><img src="{root}favicon.svg" alt=""><b>싸다구</b></a>
    <nav class="nav" aria-label="메뉴">{nav}</nav>
  </div>
</header>"""


def footer(root, notes, links, icons):
    home = root or "./"
    top_notes = "".join(f'<a href="{root}tips/{n["slug"]}/">{esc(n["title"])}</a>' for n in notes[:4])
    sns = "".join(
        f'<a href="{esc(s["url"])}" target="_blank" rel="noopener" aria-label="{esc(s["name"])}">{brand_svg(icons[s["icon"]])}</a>'
        for s in links["sns"] if s["icon"] in ("instagram", "threads", "x", "youtube", "github")
    )
    return f"""<footer class="site-foot">
  <div class="wrap">
    <div class="foot-grid">
      <div>
        <a class="logo" href="{home}"><img src="{root}favicon.svg" alt=""><b>싸다구</b></a>
        <p>자주 사는 것만 골라 매일 아침 가격을 적어두는 개인 장보기 노트예요. 가격은 쿠팡 파트너스 API 기준이며, 쿠폰·카드 할인이나 실시간 변동은 반영되지 않을 수 있어요.</p>
        <div class="sns">{sns}</div>
      </div>
      <div class="foot-col">
        <b>둘러보기</b>
        <a href="{home}">오늘의 가격</a><a href="{root}tips/">장보기 노트</a><a href="{root}about/">싸다구 소개</a><a href="{root}links/">링크 모음</a>
      </div>
      <div class="foot-col">
        <b>많이 읽는 노트</b>
        {top_notes}
      </div>
    </div>
    <p class="disc">이 사이트는 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</p>
    <p class="copy">© 2026 싸다구 · 만든 사람 스타차일드</p>
  </div>
</footer>"""


SCROLL_JS = "<script>const topEl=document.getElementById('top');addEventListener('scroll',()=>topEl.classList.toggle('scrolled',scrollY>4),{passive:true});</script>"


def page(path, title, desc, active, body, notes, links, icons, extra_head="", extra_js=""):
    depth = path.count("/")
    root = "../" * depth
    return (
        page_head(title, desc, path.replace("index.html", ""), root, extra_head)
        + header(root, active) + "\n"
        + body + "\n"
        + footer(root, notes, links, icons) + "\n"
        + SCROLL_JS + extra_js + "\n</body>\n</html>\n"
    )


def note_card(n, root, feature=False):
    cover = f'<div class="cover {n["cat"]}">{svg(NOTE_ICONS.get(n["icon"], NOTE_ICONS["tag"]))}</div>'
    meta = f'<div class="meta-row"><span>{n["read"]}분 읽기</span></div>'
    href = f'{root}tips/{n["slug"]}/'
    if feature:
        return f"""<a class="note-feature" href="{href}" data-cat="{esc(n['category'])}" data-slug="{n['slug']}">
  {cover}
  <div>
    <span class="cat-label {n['cat']}">{esc(n['category'])}</span>
    <h2>{esc(n['title'])}</h2>
    <p>{esc(n['description'])}</p>
    <div class="meta-row">{n['read']}분 읽기 · {korean_date(n['date'])}</div>
    <span class="go">읽어보기 <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
  </div>
</a>"""
    return f"""<a class="note" href="{href}" data-cat="{esc(n['category'])}" data-slug="{n['slug']}">
  {cover}
  <span class="cat-label {n['cat']}" style="display:block;margin-top:14px">{esc(n['category'])}</span>
  <h3 style="margin-top:4px">{esc(n['title'])}</h3>
  <p>{esc(n['description'])}</p>
  {meta}
</a>"""


# ---------- 페이지들 ----------

def build_tips_index(notes, links, icons):
    root = "../"
    feature = notes[0]
    counts = {c: sum(1 for n in notes if n["category"] == c) for c in CATS}
    chips = f'<button class="chip" data-cat="전체" aria-pressed="true">전체<span class="cnt num">{len(notes)}</span></button>' + "".join(
        f'<button class="chip" data-cat="{esc(c)}" aria-pressed="false">{esc(c)}<span class="cnt num">{counts[c]}</span></button>' for c in CATS
    )
    body = f"""<main class="wrap">
  <header class="page-head">
    <div class="eyebrow">장보기 노트</div>
    <h1>덜 쓰고, 더 잘 먹는 법</h1>
    <p>쿠팡에서 싸게 사는 습관부터 재료 고르는 법, 보관과 식단까지. 장보기가 조금 더 똑똑해지는 이야기를 모았어요.</p>
  </header>
  <section class="sec" style="margin-top:24px">
    {note_card(feature, root, feature=True)}
  </section>
  <section class="sec" aria-labelledby="h-notes">
    <h2 class="sec-title" id="h-notes">모든 노트</h2>
    <p class="sec-desc">카테고리를 골라서 볼 수 있어요</p>
    <div class="chips" id="chips" role="group" aria-label="카테고리" style="margin-bottom:22px">{chips}</div>
    <div class="notes" id="notes">{"".join(note_card(n, root) for n in notes)}</div>
  </section>
</main>"""
    js = f"""<script>
const FEATURE = '{feature["slug"]}';
function filter(cat) {{
  document.querySelectorAll('#chips .chip').forEach(c => c.setAttribute('aria-pressed', c.dataset.cat === cat));
  document.querySelectorAll('#notes .note').forEach(n => {{
    const show = cat === '전체' ? n.dataset.slug !== FEATURE : n.dataset.cat === cat;
    n.hidden = !show;
  }});
}}
document.getElementById('chips').addEventListener('click', e => {{ const c = e.target.closest('.chip'); if (c) filter(c.dataset.cat); }});
filter('전체');
</script>"""
    return page("tips/index.html", "장보기 노트 · 싸다구", "쿠팡 싸게 사는 습관, 재료 고르는 법, 보관과 식단까지. 장보기가 똑똑해지는 싸다구의 노트.", "tips", body, notes, links, icons, extra_js=js)


RELATED_JS = """<script>
(() => {
  const box = document.getElementById('related');
  if (!box) return;
  const want = JSON.parse(box.dataset.names);
  const ROOT = '__ROOT__';
  const DATA = location.hostname.endsWith('.github.io') ? '__REMOTE__' : ROOT + 'data';
  const ICONS = __ICONS__;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const icon = c => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[c] || ICONS._}</svg>`;
  const b = '?_=' + Date.now();
  Promise.all([fetch(DATA + '/products.json' + b).then(r => r.json()), fetch(DATA + '/prices.json' + b).then(r => r.json())])
    .then(([{ products }, { history = {}, meta = {} }]) => {
      const list = want.map(n => products.find(p => p.name === n)).filter(Boolean);
      if (!list.length) { box.remove(); return; }
      box.querySelector('.rel-list').innerHTML = list.map(p => {
        const h = history[p.name] || [], m = meta[p.name] || {};
        const price = h.length ? Math.round(h[h.length - 1].price).toLocaleString('ko-KR') + '원' : '';
        const img = m.image ? `<img src="${esc(m.image)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentNode.classList.remove('has-img');this.remove()">` : icon(p.category);
        return `<a class="rel" href="${ROOT}#${encodeURIComponent(p.name)}">
          <span class="th${m.image ? ' has-img' : ''}">${img}</span>
          <span><b>${esc(p.name)}</b><small>${esc(p.category || '')}</small></span>
          <span class="pr num${price ? '' : ' none'}">${price || '기록 대기'}</span></a>`;
      }).join('');
      box.hidden = false;
    }).catch(() => box.remove());
})();
(() => {
  const links = [...document.querySelectorAll('.toc a')];
  if (!links.length || !('IntersectionObserver' in window)) return;
  const map = new Map(links.map(a => [decodeURIComponent(a.hash.slice(1)), a]));
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { links.forEach(a => a.classList.remove('on')); map.get(e.target.id)?.classList.add('on'); }
  }), { rootMargin: '-80px 0px -70% 0px' });
  document.querySelectorAll('.prose h2[id]').forEach(h => io.observe(h));
})();
</script>"""


def build_note(n, notes, links, icons):
    root = "../../"
    toc = "".join(f'<a href="#{esc(t["id"])}">{t["name"]}</a>' for t in n["toc"])
    related = ""
    if n["related"]:
        related = f"""<section class="related" id="related" hidden data-names='{esc(json.dumps(n["related"], ensure_ascii=False))}'>
      <h2>싸다구에서 지켜보는 관련 상품</h2>
      <p>매일 아침 기록하는 가격이에요. 누르면 가격 그래프를 볼 수 있어요.</p>
      <div class="rel-list"></div>
    </section>"""
    others = [x for x in notes if x["slug"] != n["slug"]]
    same = [x for x in others if x["category"] == n["category"]]
    more = (same + [x for x in others if x not in same])[:3]
    body = f"""<main class="wrap">
  <div class="article">
    <article>
      <nav class="crumbs" aria-label="위치"><a href="{root}tips/">장보기 노트</a><span aria-hidden="true">›</span><span>{esc(n['category'])}</span></nav>
      <header class="a-head">
        <h1>{esc(n['title'])}</h1>
        <p class="lead">{esc(n['description'])}</p>
        <div class="meta-row"><span class="cat-label {n['cat']}">{esc(n['category'])}</span><span>·</span><span>{n['read']}분 읽기</span><span>·</span><time datetime="{n['date']}">{korean_date(n['date'])}</time></div>
      </header>
      <div class="cover a-cover {n['cat']}">{svg(NOTE_ICONS.get(n['icon'], NOTE_ICONS['tag']))}</div>
      <div class="prose">
{n['html']}
      </div>
      {related}
    </article>
    <aside class="toc" aria-label="목차"><b>이 글의 목차</b>{toc}</aside>
  </div>
  <section class="more-notes" aria-labelledby="h-more">
    <h2 class="sec-title" id="h-more">다른 노트도 읽어보세요</h2>
    <p class="sec-desc">장보기가 조금 더 쉬워지는 이야기</p>
    <div class="notes">{"".join(note_card(x, root) for x in more)}</div>
  </section>
</main>"""
    js = ""
    if n["related"] or n["toc"]:
        js = (RELATED_JS.replace("__ROOT__", root).replace("__REMOTE__", DATA_REMOTE)
              .replace("__ICONS__", json.dumps(PRODUCT_ICONS, ensure_ascii=False)))
    title = f"{n['title']} · 싸다구"
    return page(f"tips/{n['slug']}/index.html", title, n["description"], "tips", body, notes, links, icons, extra_js=js)


def link_card(item, icon_html, color, sub="", tag=""):
    return f"""<a class="lk" href="{esc(item['url'])}" target="_blank" rel="noopener">
  <span class="ic" style="background:{color}">{icon_html}</span>
  <span><b>{esc(item['name'])}</b>{f'<span class="h">{esc(sub)}</span>' if sub else ''}<p>{esc(item['desc'])}</p></span>
  {f'<span class="tag">{esc(tag)}</span>' if tag else '<span class="arrow" aria-hidden="true">↗</span>'}
</a>"""


def build_links(notes, links, icons):
    sns = "".join(
        link_card(s, brand_svg(icons[s["icon"]]) if s["icon"] else esc(s.get("initial", s["name"][0])), s["color"], sub=s["handle"])
        for s in links["sns"]
    )
    projects = "".join(link_card(p, esc(p["initial"]), p["color"], sub=p["url"].split("//")[1].rstrip("/"), tag=p["tag"]) for p in links["projects"])
    partners = "".join(
        link_card(p, esc(p["name"][0]), PARTNER_COLORS[i % len(PARTNER_COLORS)], sub=p["url"].split("//")[1].rstrip("/"), tag=p["tag"])
        for i, p in enumerate(links["partners"])
    )
    body = f"""<main class="wrap">
  <header class="page-head">
    <div class="eyebrow">링크 모음</div>
    <h1>싸다구 밖에서도 만나요</h1>
    <p>만든 사람의 SNS와 직접 운영하는 사이트, 함께하는 파트너 사이트를 한곳에 모았어요.</p>
    <div class="chips" style="margin-top:18px">
      <a class="chip" href="#sns" style="text-decoration:none">SNS <span class="cnt num">{len(links['sns'])}</span></a>
      <a class="chip" href="#projects" style="text-decoration:none">직접 만든 사이트 <span class="cnt num">{len(links['projects'])}</span></a>
      <a class="chip" href="#partners" style="text-decoration:none">파트너 사이트 <span class="cnt num">{len(links['partners'])}</span></a>
    </div>
  </header>
  <section class="sec" id="sns" aria-labelledby="h-sns">
    <h2 class="sec-title" id="h-sns">SNS</h2>
    <p class="sec-desc">일상과 개발, 트레이딩 이야기를 나눠요</p>
    <div class="links three">{sns}</div>
  </section>
  <section class="sec" id="projects" aria-labelledby="h-projects">
    <h2 class="sec-title" id="h-projects">직접 만든 사이트</h2>
    <p class="sec-desc">싸다구를 만든 사람이 함께 운영하는 곳이에요</p>
    <div class="links three">{projects}</div>
  </section>
  <section class="sec" id="partners" aria-labelledby="h-partners">
    <h2 class="sec-title" id="h-partners">파트너 사이트</h2>
    <p class="sec-desc">살림, 금융, 테크까지 알아두면 좋은 정보들</p>
    <div class="links three">{partners}</div>
  </section>
</main>"""
    return page("links/index.html", "링크 모음 · 싸다구", "싸다구를 만든 사람의 SNS와 직접 운영하는 사이트, 파트너 사이트 모음.", "links", body, notes, links, icons)


def build_about(notes, links, icons):
    root = "../"
    legend = [
        ("deal", "역대 최저", "지금 가격이 지금까지 기록된 가격 중 <b>가장 낮아요.</b> 필요한 물건이면 지금이 기회예요."),
        ("good", "싸다구 타이밍", "최저가와 최고가 사이에서 <b>아래쪽 30% 안</b>에 있어요. 필요하면 지금 사도 좋아요."),
        ("mute", "보통 가격", "딱 <b>평소 가격</b>이에요. 급하지 않으면 조금 기다려봐도 좋아요."),
        ("dark", "존버 추천", "최저가와 최고가 사이에서 <b>위쪽 30% 안</b>, 비싼 편이에요. 조금 기다려봐요."),
        ("mute", "변동 없음", "기록하는 동안 <b>가격이 한 번도 안 바뀌었어요.</b>"),
        ("mute", "기록 중", "기록이 <b>3번 미만</b>이라 아직 판단하지 않아요."),
        ("mute", "첫 기록 대기", "새로 추가된 상품이에요. <b>다음 날 아침</b> 첫 가격이 기록돼요."),
    ]
    legend_html = "".join(f'<div><span class="badge {t}">{l}</span><p>{d}</p></div>' for t, l, d in legend)
    faq = [
        ("쿠팡에서 본 가격이랑 달라요.", "싸다구의 가격은 매일 오전 9시쯤 쿠팡 파트너스 API로 확인한 값이에요. 그 뒤에 가격이 바뀌었거나, 쿠폰·카드 할인, 회원 혜택처럼 사람마다 다른 할인은 반영되지 않아서 차이가 날 수 있어요. 구매 전에는 쿠팡에서 최종 가격을 꼭 확인해 주세요."),
        ("왜 이 상품들만 있어요?", "싸다구는 만든 사람이 자주 사거나 눈여겨보는 상품만 골라 기록하는 개인 장보기 노트예요. 쿠팡 파트너스 API의 호출 제한을 지키기 위해 하루 한 번, 최대 20개 상품까지만 기록하고 있어요."),
        ("판단 배지는 어떻게 정해져요?", "기록된 가격 중 최저가와 최고가 사이에서 지금 가격이 어디쯤인지로 정해요. 기록이 3번 이상 쌓여야 판단하고, 기록이 쌓일수록 더 정확해져요."),
        ("'쿠팡에서 보기' 링크는 뭔가요?", "쿠팡 파트너스 링크예요. 이 링크를 통해 구매가 이루어지면 싸다구가 일정액의 수수료를 받을 수 있어요. 구매하시는 분이 내는 가격은 똑같아요. 아직 첫 기록 전인 상품은 일반 쿠팡 검색 링크로 연결돼요."),
        ("가격이 떨어지면 알림도 받을 수 있나요?", "아직은 없어요. 대신 매일 아침 가격과 판단 배지가 새로 바뀌니, 즐겨찾기해 두고 필요할 때 들러 주세요."),
    ]
    faq_html = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faq)
    body = f"""<main class="wrap">
  <header class="page-head">
    <div class="eyebrow">싸다구 소개</div>
    <h1>쌀 때 사고,<br>비쌀 땐 존버해요</h1>
    <p>싸다구는 자주 사는 쿠팡 상품만 골라 매일 아침 가격을 적어두는 작은 장보기 노트예요. 같은 물건을 더 싸게 사는 가장 확실한 방법은 <b>평소 가격을 아는 것</b>이니까요.</p>
  </header>
  <section class="sec" aria-labelledby="h-how">
    <h2 class="sec-title" id="h-how">이렇게 동작해요</h2>
    <p class="sec-desc">사람이 하나하나 확인하지 않아도 매일 자동으로 기록돼요</p>
    <div class="steps">
      <div class="step"><h3>매일 아침 가격 확인</h3><p>매일 오전 9시쯤, 쿠팡 파트너스 API로 상품마다 한 번씩 가격을 확인해요. 호출 사이에는 넉넉히 쉬어서 제한을 지켜요.</p></div>
      <div class="step"><h3>같은 상품인지 확인 후 기록</h3><p>상품명과 상품 ID가 정확히 같은 경우에만 가격을 기록해요. 비슷한 다른 상품의 가격이 섞이지 않아요.</p></div>
      <div class="step"><h3>쌓일수록 똑똑하게</h3><p>기록이 3번 이상 쌓이면 지금 가격이 싼 편인지 비싼 편인지 판단해서 배지로 알려드려요.</p></div>
    </div>
  </section>
  <section class="sec" aria-labelledby="h-legend">
    <h2 class="sec-title" id="h-legend">배지 읽는 법</h2>
    <p class="sec-desc">상품 사진 왼쪽 위에 붙는 배지의 뜻이에요</p>
    <div class="legend">{legend_html}</div>
  </section>
  <section class="sec" aria-labelledby="h-faq">
    <h2 class="sec-title" id="h-faq">자주 묻는 질문</h2>
    <p class="sec-desc">궁금한 게 더 있으면 SNS로 편하게 물어봐 주세요</p>
    <div class="faq">{faq_html}</div>
  </section>
  <section class="sec" aria-labelledby="h-maker">
    <h2 class="sec-title" id="h-maker">만든 사람</h2>
    <p class="sec-desc">스타차일드 · 개발하고, 기록하고, 가끔 장을 봐요</p>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <a class="btn" href="{root}links/">SNS와 사이트 보기</a>
      <a class="btn ghost" href="{root}tips/">장보기 노트 읽기</a>
    </div>
  </section>
</main>"""
    return page("about/index.html", "싸다구 소개 · 쌀 때 사다구", "싸다구가 가격을 기록하는 방법, 배지 읽는 법, 자주 묻는 질문.", "about", body, notes, links, icons)


def build_404(notes, links, icons):
    body = f"""<main class="wrap" style="text-align:center;padding:72px 16px 24px">
  <img src="{SITE_BASE}favicon.svg" alt="" style="width:88px;height:88px;transform:rotate(-8deg)">
  <h1 style="margin:22px 0 8px;font-size:30px;font-weight:800;letter-spacing:-0.04em">여긴 아무것도 없다구</h1>
  <p style="margin:0;color:var(--muted)">주소가 바뀌었거나 사라진 페이지예요.</p>
  <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:24px">
    <a class="btn" href="{SITE_BASE}">오늘의 가격 보기</a>
    <a class="btn ghost" href="{SITE_BASE}tips/">장보기 노트</a>
  </div>
</main>"""
    # 404는 어느 주소에서든 열리므로 절대 경로로 만듭니다
    html_ = (page_head("페이지를 찾을 수 없어요 · 싸다구", "요청한 페이지를 찾을 수 없어요.", "404.html", SITE_BASE)
             + header(SITE_BASE, "") + "\n" + body + "\n" + footer(SITE_BASE, notes, links, icons) + "\n" + SCROLL_JS + "\n</body>\n</html>\n")
    return html_


def build_sitemap(notes):
    urls = ["", "tips/", "about/", "links/"] + [f"tips/{n['slug']}/" for n in notes]
    items = "".join(f"  <url><loc>{SITE_URL}{u}</loc></url>\n" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}</urlset>\n'


def update_index(notes, links, icons):
    path = ROOT / "index.html"
    s = path.read_text(encoding="utf-8")
    s = re.sub(r"<!-- @header -->.*?<!-- /@header -->", lambda m: "<!-- @header -->\n" + header("", "home") + "\n<!-- /@header -->", s, flags=re.S)
    s = re.sub(r"<!-- @footer -->.*?<!-- /@footer -->", lambda m: "<!-- @footer -->\n" + footer("", notes, links, icons) + "\n<!-- /@footer -->", s, flags=re.S)
    path.write_text(s, encoding="utf-8")


def write(rel, content):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print("  ✓", rel)


def main():
    notes = sorted((parse_note(p) for p in (ROOT / "content/tips").glob("*.md")), key=lambda n: n["order"])
    links = json.loads((ROOT / "content/links.json").read_text(encoding="utf-8"))
    icons = json.loads((ROOT / "content/brand-icons.json").read_text(encoding="utf-8"))
    print(f"노트 {len(notes)}편으로 페이지를 만듭니다")
    write("tips/index.html", build_tips_index(notes, links, icons))
    for n in notes:
        write(f"tips/{n['slug']}/index.html", build_note(n, notes, links, icons))
    write("links/index.html", build_links(notes, links, icons))
    write("about/index.html", build_about(notes, links, icons))
    write("404.html", build_404(notes, links, icons))
    write("sitemap.xml", build_sitemap(notes))
    update_index(notes, links, icons)
    print("  ✓ index.html (메뉴·꼬리말)")


if __name__ == "__main__":
    main()
