#!/usr/bin/env python3
"""싸다구 페이지 생성기

content/tips/*.md (장보기 노트)와 content/links.json (링크 모음)으로
tips/, links/, about/, 404.html, sitemap.xml, tips/feed.xml을 만들고,
index.html의 메뉴·꼬리말·검색엔진 정보를 다른 페이지와 똑같이 맞춥니다.

    pip install markdown
    python3 scripts/build_site.py
    node scripts/make_og.cjs          # (선택) 글마다 공유 이미지 만들기
    python3 scripts/build_site.py     # 공유 이미지를 페이지에 연결
"""
import datetime
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
AUTHOR = "스타차일드"

# 카테고리: 이름 → (주소·색 이름, 소개, 대표 아이콘)
CATS = {
    "쇼핑 팁": ("shop", "같은 물건을 더 싸게 사는 습관과 요령", "tag"),
    "재료 고르기": ("fresh", "신선하고 맛있는 재료를 고르는 눈", "leaf"),
    "보관·요리": ("kitchen", "사 온 재료를 끝까지 맛있게 쓰는 법", "fridge"),
    "레시피": ("recipe", "집에 있는 재료로 뚝딱 만드는 한 끼", "bowl"),
    "살림": ("home", "세탁·청소·생활용품을 똑똑하게", "house"),
}

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
    "egg": '<path d="M12 3c3.6 0 6.5 5 6.5 9.5a6.5 6.5 0 0 1-13 0C5.5 8 8.4 3 12 3Z"/>',
    "apple": '<path d="M12 7.5c-1.5-1-5.5-1.3-6.8 2-1.2 3.2.5 8 2.8 9.8 1.2.9 2.4.9 4 .2 1.6.7 2.8.7 4-.2 2.3-1.8 4-6.6 2.8-9.8-1.3-3.3-5.3-3-6.8-2Z"/><path d="M12 7.5c0-2 .8-3.3 2.5-4"/>',
    "citrus": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="5.5"/><path d="M12 6.5v11M6.5 12h11M8.1 8.1l7.8 7.8M15.9 8.1l-7.8 7.8"/>',
    "berry": '<path d="M12 7.5c4.5 0 7 1.8 7 4.5 0 4-3.8 8.5-7 8.5S5 16 5 12c0-2.7 2.5-4.5 7-4.5Z"/><path d="M8.5 4.5 12 7.5l3.5-3M12 7.5V3"/><path d="M9 12h.01M12 14h.01M15 12h.01M10.5 16.5h.01M13.5 16.5h.01"/>',
    "bowl": '<path d="M3.5 11h17a8.5 8.5 0 0 1-17 0Z"/><path d="M8 8.5c1.2-1.4 2.6-2 4-2s2.8.6 4 2"/>',
    "noodle": '<path d="M3.5 12h17a8.5 8.5 0 0 1-17 0Z"/><path d="M14 3l-4 9M19 4l-6.5 8"/>',
    "milk": '<path d="M8 3h8v3l2 3v12H6V9l2-3V3Z"/><path d="M6 9h12M8 6h8"/>',
    "cheese": '<path d="M3.5 17.5V11L17 5.5l3.5 5.5v6.5Z"/><path d="M3.5 11h17"/><circle cx="9" cy="14.5" r="1.2"/><circle cx="15" cy="15" r="1"/>',
    "bottle": '<path d="M10 2.5h4v3.2c0 .6.3 1.1.7 1.5l.9.9c.9.9 1.4 2.1 1.4 3.3V19a2.5 2.5 0 0 1-2.5 2.5h-5A2.5 2.5 0 0 1 7 19v-7.6c0-1.2.5-2.4 1.4-3.3l.9-.9c.4-.4.7-.9.7-1.5Z"/><path d="M7 13h10"/>',
    "jar": '<path d="M7 4.5h10M8 4.5V7l-1.5 2v10.5A1.5 1.5 0 0 0 8 21h8a1.5 1.5 0 0 0 1.5-1.5V9L16 7V4.5"/><path d="M6.5 12h11"/>',
    "fridge": '<rect x="5.5" y="2.5" width="13" height="19" rx="2.5"/><path d="M5.5 10h13M8.5 6v1.5M8.5 13v3"/>',
    "bread": '<path d="M5 10.5C3.5 10 3 8.8 3 8c0-2.2 3.6-4 9-4s9 1.8 9 4c0 .8-.5 2-2 2.5V19a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 5 19Z"/>',
    "knife": '<path d="M3 20.5 14.5 9l2 2L8 19.5a3 3 0 0 1-2 .9Z"/><path d="m14.5 9 4-4a2 2 0 0 1 2.8 2.8l-4 4"/>',
    "spoon": '<ellipse cx="8" cy="8" rx="4.5" ry="5.5" transform="rotate(-45 8 8)"/><path d="m11.2 11.2 9.3 9.3"/>',
    "pan": '<circle cx="10" cy="13" r="6.5"/><path d="M16.2 11 21.5 8.5"/>',
    "trash": '<path d="M4 7h16M9.5 7V4.5h5V7M6 7l1 13h10l1-13"/><path d="M10 11v5M14 11v5"/>',
    "shirt": '<path d="M8.5 3.5 3.5 6l2 4 2-1V20h9V9l2 1 2-4-5-2.5a3.5 3.5 0 0 1-7 0Z"/>',
    "drop": '<path d="M12 3.2s6 6.4 6 10.8a6 6 0 0 1-12 0c0-4.4 6-10.8 6-10.8Z"/><path d="M9.3 14.5a2.8 2.8 0 0 0 2.2 2.6"/>',
    "sparkle": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18"/>',
    "flame": '<path d="M12 21c-3.6 0-6-2.4-6-5.6 0-4.4 4.2-6 4.5-11 2.8 2 4 4.2 4 6.5.9-.6 1.5-1.5 1.8-2.5 1.2 1.4 1.7 3.3 1.7 5 0 4.6-2.4 7.6-6 7.6Z"/>',
    "receipt": '<path d="M6 3h12v18l-2.5-1.5L13 21l-2-1.5L8.5 21 6 19.5Z"/><path d="M9 8h6M9 12h6M9 16h3"/>',
    "list": '<rect x="4.5" y="3.5" width="15" height="17" rx="2"/><path d="M8 8.5h8M8 12.5h8M8 16.5h5"/>',
    "star": '<path d="m12 3.5 2.6 5.4 5.9.8-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.8Z"/>',
    "card": '<rect x="3" y="5.5" width="18" height="13" rx="2.5"/><path d="M3 10h18M7 15h3"/>',
    "truck": '<path d="M2.5 6.5h11v9h-11ZM13.5 9.5h4l3 3v3h-7"/><circle cx="6.5" cy="17.5" r="1.8"/><circle cx="16.5" cy="17.5" r="1.8"/>',
    "percent": '<path d="M19 5 5 19"/><circle cx="7" cy="7" r="2.5"/><circle cx="17" cy="17" r="2.5"/>',
    "house": '<path d="M3.5 11 12 4l8.5 7M6 9.5V20h12V9.5"/><path d="M10 20v-5h4v5"/>',
    "bulb": '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3Z"/>',
    "water": '<path d="M9.5 2.5h5M10 2.5v2.5L8 8v12.5a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V8l-2-3V2.5"/><path d="M8 12h8"/>',
    "paw": '<circle cx="6.3" cy="10.3" r="1.7"/><circle cx="9.8" cy="6.6" r="1.7"/><circle cx="14.2" cy="6.6" r="1.7"/><circle cx="17.7" cy="10.3" r="1.7"/><path d="M12 11.3c-2.9 0-5.4 3.1-5.4 5.4 0 1.5 1.2 2.3 2.7 2.3 1.1 0 1.7-.5 2.7-.5s1.6.5 2.7.5c1.5 0 2.7-.8 2.7-2.3 0-2.3-2.5-5.4-5.4-5.4Z"/>',
}

# 상품 카테고리 아이콘 (index.html과 같은 모양)
PRODUCT_ICONS = {
    "먹거리": '<path d="M3.5 11.5h17a8.5 8.5 0 0 1-17 0Z"/><path d="M8.5 8c0-1.2 1.2-1.6 1.2-2.8M12.5 8c0-1.2 1.2-1.6 1.2-2.8M16.5 8c0-1.2 1.2-1.6 1.2-2.8"/>',
    "음료": '<path d="M6.5 8h11l-1.3 12a1.2 1.2 0 0 1-1.2 1H9a1.2 1.2 0 0 1-1.2-1L6.5 8Z"/><path d="M5.5 8h13M12.5 8l1.6-5H17"/>',
    "뷰티·건강": NOTE_ICONS["drop"],
    "반려견": NOTE_ICONS["paw"],
    "생활용품": '<path d="M9.5 3h4v3h-4z"/><path d="M8 6h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2Z"/><path d="M17 9.5h1a1.5 1.5 0 0 1 1.5 1.5v2.5M9 12h5"/>',
    "_": NOTE_ICONS["tag"],
}

CALLOUTS = {"팁": "tip", "주의": "warn", "한 줄 요약": "sum", "공식": "sum", "참고": "note"}
SECTION_COLORS = {
    "gov": "#1D4ED8", "price": "#0F8A43", "market": "#E8590C", "korean": "#D9480F", "world": "#7048E8",
    "nutrition": "#0E9F6E", "safety": "#C2255C", "home": "#6D28D9", "partners": "#364FC7",
}
PARTNER_COLORS = ["#2F6FEB", "#0E9F6E", "#E8590C", "#7048E8", "#C2255C", "#1098AD", "#5C940D", "#D6336C", "#364FC7", "#AE3EC9", "#F08C00"]
SEARCH_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>'


def esc(s):
    return html.escape(str(s), quote=True)


def svg(paths):
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths}</svg>'


def brand_svg(path):
    return f'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="{path}"/></svg>'


def korean_date(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{y}년 {m}월 {d}일"


def ld(obj):
    """검색엔진용 구조화 데이터 (JSON-LD)"""
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


# ---------- 콘텐츠 읽기 ----------

def parse_note(path):
    text = path.read_text(encoding="utf-8")
    _, fm, body = text.split("---", 2)
    meta = {}
    for line in fm.strip().splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    meta["slug"] = path.stem
    meta["order"] = int(meta.get("order", 999))
    meta["related"] = [x.strip() for x in meta.get("related", "").split(",") if x.strip()]
    meta["ingredients"] = [x.strip() for x in meta.get("ingredients", "").split("|") if x.strip()]
    meta["cat"] = CATS.get(meta["category"], CATS["쇼핑 팁"])[0]

    md = markdown.Markdown(
        extensions=["tables", "toc", "sane_lists"],
        extension_configs={"toc": {"slugify": slugify_unicode, "toc_depth": "2"}},
    )
    # 연달아 쓴 인용 상자(> **팁** 다음 > **한 줄 요약**)가 하나로 합쳐지지 않게 구분
    body = re.sub(r"(^>.*\n)\n(?=> )", "\\1\n<!-- -->\n\n", body, flags=re.M)
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
    chars = len(re.sub(r"\s+", "", strip_tags(out)))
    meta["chars"] = chars
    meta["read"] = max(1, math.ceil(chars / 500))
    # 레시피: '만드는 법' 아래 번호 목록을 조리 순서로 사용
    steps = re.search(r'<h2 id="[^"]*">만드는 법</h2>\s*<ol>(.*?)</ol>', out, re.S)
    meta["steps"] = [strip_tags(x) for x in re.findall(r"<li>(.*?)</li>", steps.group(1), re.S)] if steps else []
    og = ROOT / "og" / "tips" / f"{path.stem}.png"
    meta["og"] = f"og/tips/{path.stem}.png" if og.exists() else "og.png"
    return meta


def _flatten(tokens):
    for t in tokens:
        yield t
        yield from _flatten(t.get("children", []))


# ---------- 공통 조각 ----------

def page_head(title, desc, path, root, image="og.png", extra="", og_type="website"):
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE_URL}{path}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="theme-color" content="#F6F5F0" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#111113" media="(prefers-color-scheme: dark)">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="싸다구">
<meta property="og:locale" content="ko_KR">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{SITE_URL}{path}">
<meta property="og:image" content="{SITE_URL}{image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{SITE_URL}{image}">
<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
<link rel="icon" href="{root}favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{root}apple-touch-icon.png">
<link rel="alternate" type="application/rss+xml" title="싸다구 장보기 노트" href="{SITE_URL}tips/feed.xml">
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
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
    <a class="logo" href="{home}" aria-label="싸다구 홈"><img src="{root}favicon.svg" alt="" width="30" height="30"><b>싸다구</b></a>
    <nav class="nav" aria-label="메뉴">{nav}</nav>
  </div>
</header>"""


def footer(root, notes, links, icons):
    home = root or "./"
    picks = [n for n in notes if n["order"] <= 10][:4]
    top_notes = "".join(f'<a href="{root}tips/{n["slug"]}/">{esc(n["title"])}</a>' for n in picks)
    cats = "".join(f'<a href="{root}tips/c/{v[0]}/">{esc(k)}</a>' for k, v in CATS.items())
    sns = "".join(
        f'<a href="{esc(s["url"])}" target="_blank" rel="noopener" aria-label="{esc(s["name"])}">{brand_svg(icons[s["icon"]])}</a>'
        for s in links["sns"] if s["icon"] in ("instagram", "threads", "x", "youtube", "github")
    )
    return f"""<footer class="site-foot">
  <div class="wrap">
    <div class="foot-grid">
      <div>
        <a class="logo" href="{home}"><img src="{root}favicon.svg" alt="" width="26" height="26"><b>싸다구</b></a>
        <p>자주 사는 것만 골라 매일 아침 가격을 적어두는 개인 장보기 노트예요. 가격은 쿠팡 파트너스 API 기준이며, 쿠폰·카드 할인이나 실시간 변동은 반영되지 않을 수 있어요.</p>
        <div class="sns">{sns}</div>
      </div>
      <div class="foot-col">
        <b>둘러보기</b>
        <a href="{home}">오늘의 가격</a><a href="{root}tips/">장보기 노트</a><a href="{root}about/">싸다구 소개</a><a href="{root}links/">링크 모음</a>
      </div>
      <div class="foot-col">
        <b>노트 카테고리</b>
        {cats}
      </div>
    </div>
    <div class="foot-col" style="margin-top:24px"><b>많이 읽는 노트</b>{top_notes}</div>
    <p class="disc">이 사이트는 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</p>
    <p class="copy">© 2026 싸다구 · 만든 사람 {AUTHOR}</p>
  </div>
</footer>"""


SCROLL_JS = "<script>const topEl=document.getElementById('top');addEventListener('scroll',()=>topEl.classList.toggle('scrolled',scrollY>4),{passive:true});</script>"


def page(path, title, desc, active, body, notes, links, icons, extra_head="", extra_js="", image="og.png", og_type="website"):
    depth = path.count("/")
    root = "../" * depth
    return (
        page_head(title, desc, path.replace("index.html", ""), root, image, extra_head, og_type)
        + header(root, active) + "\n"
        + body + "\n"
        + footer(root, notes, links, icons) + "\n"
        + SCROLL_JS + extra_js + "\n</body>\n</html>\n"
    )


def cover(n):
    return f'<div class="cover {n["cat"]}">{svg(NOTE_ICONS.get(n["icon"], NOTE_ICONS["tag"]))}</div>'


def note_card(n, root):
    return f"""<a class="note" href="{root}tips/{n['slug']}/">
  {cover(n)}
  <span class="cat-label {n['cat']}" style="display:block;margin-top:14px">{esc(n['category'])}</span>
  <h3 style="margin-top:4px">{esc(n['title'])}</h3>
  <p>{esc(n['description'])}</p>
  <div class="meta-row"><span>{n['read']}분 읽기</span></div>
</a>"""


def note_row(n, root):
    text = esc(f"{n['title']} {n['description']} {n['category']}")
    return f"""<a class="row" href="{root}tips/{n['slug']}/" data-q="{text}">
  {cover(n)}
  <span><span class="cat-label {n['cat']}">{esc(n['category'])}</span><h3>{esc(n['title'])}</h3><p>{esc(n['description'])}</p></span>
</a>"""


def feature_card(n, root):
    return f"""<a class="note-feature" href="{root}tips/{n['slug']}/">
  {cover(n)}
  <div>
    <span class="cat-label {n['cat']}">{esc(n['category'])} · 추천 노트</span>
    <h2>{esc(n['title'])}</h2>
    <p>{esc(n['description'])}</p>
    <div class="meta-row">{n['read']}분 읽기 · {korean_date(n['date'])}</div>
    <span class="go">읽어보기 <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
  </div>
</a>"""


def breadcrumb_ld(items):
    return ld({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": name, "item": SITE_URL + url} for i, (name, url) in enumerate(items)],
    })


SEARCH_JS = """<script>
(() => {
  const input = document.getElementById('q'), rows = [...document.querySelectorAll('#rows .row')];
  const count = document.getElementById('count'), empty = document.getElementById('empty');
  if (!input) return;
  const run = () => {
    const words = input.value.trim().toLowerCase().split(/\\s+/).filter(Boolean);
    let shown = 0;
    rows.forEach(r => { const ok = words.every(w => r.dataset.q.toLowerCase().includes(w)); r.hidden = !ok; if (ok) shown++; });
    count.textContent = `${shown}편`;
    empty.hidden = shown > 0;
  };
  input.addEventListener('input', run);
  const q = new URLSearchParams(location.search).get('q');
  if (q) { input.value = q; run(); }
})();
</script>"""


def list_section(notes, root, heading, placeholder):
    return f"""<section class="sec" aria-labelledby="h-list">
    <div class="list-head">
      <div><h2 class="sec-title" id="h-list">{heading}</h2><p class="list-count" id="count" style="margin:0">{len(notes)}편</p></div>
      <label class="search"><span class="sr">노트 검색</span>{SEARCH_ICON}<input id="q" type="search" placeholder="{placeholder}" autocomplete="off"></label>
    </div>
    <div class="rows" id="rows">{"".join(note_row(n, root) for n in notes)}</div>
    <p class="no-result" id="empty" hidden>찾는 노트가 없어요. 다른 단어로 검색해 보세요.</p>
  </section>"""


def cat_chips(root, active, notes):
    items = [("전체", f"{root}tips/", len(notes), active == "전체")]
    for name, (slug, _, _) in CATS.items():
        items.append((name, f"{root}tips/c/{slug}/", sum(1 for n in notes if n["category"] == name), active == name))
    return '<nav class="chips" aria-label="노트 카테고리">' + "".join(
        f'<a class="chip" href="{href}"{" aria-current=" + chr(34) + "page" + chr(34) if on else ""}>{esc(name)}<span class="cnt num">{cnt}</span></a>'
        for name, href, cnt, on in items
    ) + "</nav>"


def cat_tiles(root, notes, with_desc=True):
    return "".join(
        f'<a class="cat-tile cover {slug}" href="{root}tips/c/{slug}/">{svg(NOTE_ICONS[ic])}<span><b>{esc(name)}</b>'
        f'<span>{sum(1 for n in notes if n["category"] == name)}편{" · " + esc(desc) if with_desc else ""}</span></span></a>'
        for name, (slug, desc, ic) in CATS.items()
    )


# ---------- 페이지들 ----------

def build_tips_index(notes, links, icons):
    root = "../"
    feature = notes[0]
    body = f"""<main class="wrap">
  <header class="page-head">
    <div class="eyebrow">장보기 노트</div>
    <h1>덜 쓰고, 더 잘 먹는 법</h1>
    <p>쿠팡에서 싸게 사는 습관부터 재료 고르는 법, 보관, 레시피, 살림까지. 장보기가 조금 더 똑똑해지는 이야기 {len(notes)}편을 모았어요.</p>
  </header>
  <section class="sec" style="margin-top:24px">{feature_card(feature, root)}</section>
  <section class="sec" aria-labelledby="h-cats">
    <h2 class="sec-title" id="h-cats">카테고리</h2>
    <p class="sec-desc">궁금한 주제부터 골라 읽어 보세요</p>
    <div class="cat-grid">{cat_tiles(root, notes)}</div>
  </section>
  {list_section(notes, root, "모든 노트", "예: 계란, 냉동, 김치찌개")}
</main>"""
    head = breadcrumb_ld([("싸다구", ""), ("장보기 노트", "tips/")]) + ld({
        "@context": "https://schema.org", "@type": "CollectionPage", "name": "장보기 노트", "url": SITE_URL + "tips/",
        "inLanguage": "ko-KR", "description": "쿠팡 싸게 사는 습관, 재료 고르는 법, 보관, 레시피, 살림까지.",
        "hasPart": [{"@type": "Article", "headline": n["title"], "url": f"{SITE_URL}tips/{n['slug']}/"} for n in notes],
    })
    return page("tips/index.html", "장보기 노트 · 싸다구", f"쿠팡 싸게 사는 습관, 재료 고르는 법, 보관, 레시피, 살림까지. 장보기가 똑똑해지는 노트 {len(notes)}편.",
                "tips", body, notes, links, icons, extra_head=head, extra_js=SEARCH_JS)


def build_category(name, notes_all, links, icons):
    slug, desc, ic = CATS[name]
    root = "../../../"
    notes = [n for n in notes_all if n["category"] == name]
    body = f"""<main class="wrap">
  <nav class="crumbs" aria-label="위치"><a href="{root}tips/">장보기 노트</a><span aria-hidden="true">›</span><span>{esc(name)}</span></nav>
  <header class="page-head" style="padding-top:14px">
    <div class="eyebrow cat-label {slug}">{len(notes)}편</div>
    <h1>{esc(name)}</h1>
    <p>{esc(desc)}. 싸다구 장보기 노트의 {esc(name)} 글을 모았어요.</p>
  </header>
  <div style="margin-top:18px">{cat_chips(root, name, notes_all)}</div>
  {list_section(notes, root, f"{name} 노트", "이 카테고리에서 검색")}
</main>"""
    head = breadcrumb_ld([("싸다구", ""), ("장보기 노트", "tips/"), (name, f"tips/c/{slug}/")])
    return page(f"tips/c/{slug}/index.html", f"{name} · 장보기 노트 · 싸다구", f"{desc}. 싸다구 장보기 노트의 {name} 글 {len(notes)}편.",
                "tips", body, notes_all, links, icons, extra_head=head, extra_js=SEARCH_JS)


NOTE_JS = """<script>
(() => {
  const box = document.getElementById('related');
  if (box) {
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
  }
  const links = [...document.querySelectorAll('.toc a')];
  if (links.length && 'IntersectionObserver' in window) {
    const map = new Map(links.map(a => [decodeURIComponent(a.hash.slice(1)), a]));
    const io = new IntersectionObserver(es => es.forEach(e => {
      if (e.isIntersecting) { links.forEach(a => a.classList.remove('on')); map.get(e.target.id)?.classList.add('on'); }
    }), { rootMargin: '-80px 0px -70% 0px' });
    document.querySelectorAll('.prose h2[id]').forEach(h => io.observe(h));
  }
  const toast = document.getElementById('toast');
  const say = t => { toast.textContent = t; toast.classList.add('on'); setTimeout(() => toast.classList.remove('on'), 1800); };
  const url = location.href.split('#')[0];
  document.getElementById('copy')?.addEventListener('click', () => {
    (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(() => say('링크를 복사했어요'), () => say(url));
  });
  const share = document.getElementById('share');
  if (share && navigator.share) share.hidden = false;
  share?.addEventListener('click', () => navigator.share({ title: document.title, url }).catch(() => {}));
})();
</script>"""

COPY_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></svg>'
SHARE_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12M7.5 7.5 12 3l4.5 4.5M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg>'


def build_note(n, notes, links, icons):
    root = "../../"
    url = f"{SITE_URL}tips/{n['slug']}/"
    cslug = n["cat"]
    toc = "".join(f'<a href="#{esc(t["id"])}">{t["name"]}</a>' for t in n["toc"])
    related = ""
    if n["related"]:
        related = f"""<section class="related" id="related" hidden data-names='{esc(json.dumps(n["related"], ensure_ascii=False))}'>
      <h2>싸다구에서 지켜보는 관련 상품</h2>
      <p>매일 아침 기록하는 가격이에요. 누르면 가격 그래프를 볼 수 있어요.</p>
      <div class="rel-list"></div>
    </section>"""
    recipe_meta = ""
    if n["category"] == "레시피" and (n.get("servings") or n.get("time")):
        bits = []
        if n.get("servings"):
            bits.append(f"<span>{esc(n['servings'])}</span>")
        if n.get("time"):
            bits.append(f"<span>{esc(n['time'])}분</span>")
        if n["ingredients"]:
            bits.append(f"<span>재료 {len(n['ingredients'])}가지</span>")
        recipe_meta = f'<div class="recipe-meta">{"".join(bits)}</div>'
    others = [x for x in notes if x["slug"] != n["slug"]]
    same = [x for x in others if x["category"] == n["category"]]
    # 같은 카테고리에서 바로 다음 순서의 글부터 추천 (글마다 다르게)
    same_sorted = sorted(same, key=lambda x: (x["order"] - n["order"]) % 1000)
    more = (same_sorted + [x for x in others if x not in same])[:3]
    body = f"""<main class="wrap">
  <div class="article">
    <article>
      <nav class="crumbs" aria-label="위치"><a href="{root}tips/">장보기 노트</a><span aria-hidden="true">›</span><a href="{root}tips/c/{cslug}/">{esc(n['category'])}</a></nav>
      <header class="a-head">
        <h1>{esc(n['title'])}</h1>
        <p class="lead">{esc(n['description'])}</p>
        <div class="meta-row"><span class="cat-label {cslug}">{esc(n['category'])}</span><span>·</span><span>{n['read']}분 읽기</span><span>·</span><time datetime="{n['date']}">{korean_date(n['date'])}</time></div>
        {recipe_meta}
        <div class="share"><button type="button" id="copy">{COPY_ICON}링크 복사</button><button type="button" id="share" hidden>{SHARE_ICON}공유하기</button></div>
      </header>
      <div class="cover a-cover {cslug}">{svg(NOTE_ICONS.get(n['icon'], NOTE_ICONS['tag']))}</div>
      <div class="prose">
{n['html']}
      </div>
      {related}
    </article>
    <aside class="toc" aria-label="목차"><b>이 글의 목차</b>{toc}</aside>
  </div>
  <section class="more-notes" aria-labelledby="h-more">
    <h2 class="sec-title" id="h-more">다른 노트도 읽어보세요</h2>
    <p class="sec-desc">{esc(n['category'])} 이야기를 더 모았어요</p>
    <div class="notes">{"".join(note_card(x, root) for x in more)}</div>
  </section>
</main>
<div class="toast" id="toast" role="status" aria-live="polite"></div>"""
    image = n["og"]
    article = {
        "@context": "https://schema.org", "@type": "BlogPosting",
        "headline": n["title"], "description": n["description"], "inLanguage": "ko-KR",
        "datePublished": n["date"], "dateModified": n.get("updated", n["date"]),
        "author": {"@type": "Person", "name": AUTHOR, "url": SITE_URL + "about/"},
        "publisher": {"@type": "Organization", "name": "싸다구", "logo": {"@type": "ImageObject", "url": SITE_URL + "apple-touch-icon.png"}},
        "image": SITE_URL + image, "mainEntityOfPage": url, "articleSection": n["category"],
    }
    head = ld(article) + breadcrumb_ld([("싸다구", ""), ("장보기 노트", "tips/"), (n["category"], f"tips/c/{cslug}/"), (n["title"], f"tips/{n['slug']}/")])
    if n["category"] == "레시피" and n["ingredients"] and n["steps"]:
        recipe = {
            "@context": "https://schema.org", "@type": "Recipe", "name": n["title"], "description": n["description"],
            "image": [SITE_URL + image], "author": {"@type": "Person", "name": AUTHOR}, "datePublished": n["date"],
            "recipeCategory": n.get("dish", "반찬"), "recipeCuisine": "한식", "inLanguage": "ko-KR",
            "recipeIngredient": n["ingredients"],
            "recipeInstructions": [{"@type": "HowToStep", "text": s} for s in n["steps"]],
        }
        if n.get("servings"):
            recipe["recipeYield"] = n["servings"]
        if n.get("time"):
            recipe["totalTime"] = f"PT{int(n['time'])}M"
        head += ld(recipe)
    js = NOTE_JS.replace("__ROOT__", root).replace("__REMOTE__", DATA_REMOTE).replace("__ICONS__", json.dumps(PRODUCT_ICONS, ensure_ascii=False))
    return page(f"tips/{n['slug']}/index.html", f"{n['title']} · 싸다구", n["description"], "tips", body, notes, links, icons,
                extra_head=head, extra_js=js, image=image, og_type="article")


def link_card(item, icon_html, color, sub="", tag="", small=False):
    q = esc(f"{item['name']} {item.get('desc', '')} {tag} {sub}")
    return f"""<a class="lk{' small' if small else ''}" href="{esc(item['url'])}" target="_blank" rel="noopener" data-q="{q}">
  <span class="ic" style="background:{color}">{icon_html}</span>
  <span><b>{esc(item['name'])}</b>{f'<span class="h">{esc(sub)}</span>' if sub else ''}<p>{esc(item.get('desc', ''))}</p></span>
  {f'<span class="tag">{esc(tag)}</span>' if tag else '<span class="arrow" aria-hidden="true">↗</span>'}
</a>"""


def domain(url):
    return re.sub(r"^https?://(www\.)?", "", url).rstrip("/")


LINKS_JS = """<script>
(() => {
  const input = document.getElementById('lq');
  const cards = [...document.querySelectorAll('.lk')], secs = [...document.querySelectorAll('[data-sec]')];
  const empty = document.getElementById('lempty');
  input.addEventListener('input', () => {
    const words = input.value.trim().toLowerCase().split(/\\s+/).filter(Boolean);
    cards.forEach(c => c.hidden = !words.every(w => c.dataset.q.toLowerCase().includes(w)));
    let any = false;
    secs.forEach(s => { const on = [...s.querySelectorAll('.lk')].some(c => !c.hidden); s.hidden = !on; any = any || on; });
    empty.hidden = any;
  });
})();
</script>"""


def build_links(notes, links, icons):
    sections = []
    sns = "".join(
        link_card(s, brand_svg(icons[s["icon"]]) if s["icon"] else esc(s.get("initial", s["name"][0])), s["color"], sub=s["handle"])
        for s in links["sns"]
    )
    sections.append(("sns", "SNS", "만든 사람의 일상과 개발, 트레이딩 이야기", sns))
    projects = "".join(link_card(p, esc(p["initial"]), p["color"], sub=domain(p["url"]), tag=p["tag"]) for p in links["projects"])
    sections.append(("projects", "직접 만든 사이트", "싸다구를 만든 사람이 함께 운영하는 곳이에요", projects))
    for sec in links.get("resources", []):
        color = SECTION_COLORS.get(sec["id"], "#364FC7")
        cards = "".join(link_card(it, esc(it["name"][0]), color, sub=domain(it["url"]), tag=it.get("tag", ""), small=True) for it in sec["items"])
        sections.append((sec["id"], sec["title"], sec["desc"], cards))
    partners = "".join(
        link_card(p, esc(p["name"][0]), PARTNER_COLORS[i % len(PARTNER_COLORS)], sub=domain(p["url"]), tag=p["tag"], small=True)
        for i, p in enumerate(links["partners"])
    )
    sections.append(("partners", "파트너 사이트", "살림·금융·테크까지 함께하는 이웃 블로그", partners))
    total = len(links["sns"]) + len(links["projects"]) + len(links["partners"]) + sum(len(s["items"]) for s in links.get("resources", []))
    chips = "".join(f'<a class="chip" href="#{sid}">{esc(title)}</a>' for sid, title, _, _ in sections)
    secs_html = "".join(f"""
  <section class="sec" id="{sid}" data-sec aria-labelledby="h-{sid}">
    <h2 class="sec-title" id="h-{sid}">{esc(title)}</h2>
    <p class="sec-desc">{esc(desc)}</p>
    <div class="links three">{cards}</div>
  </section>""" for sid, title, desc, cards in sections)
    body = f"""<main class="wrap">
  <header class="page-head">
    <div class="eyebrow">링크 모음 · {total}곳</div>
    <h1>장보기와 살림에 쓸모 있는 곳</h1>
    <p>식품 안전과 가격 정보를 확인할 수 있는 공식 사이트, 믿을 만한 레시피 사이트, 영양·살림 정보, 그리고 만든 사람의 SNS와 이웃 사이트까지 한곳에 모았어요.</p>
    <label class="search" style="margin-top:20px"><span class="sr">링크 검색</span>{SEARCH_ICON}<input id="lq" type="search" placeholder="예: 레시피, 가격, 식품안전" autocomplete="off"></label>
    <nav class="chips" aria-label="섹션" style="margin-top:14px">{chips}</nav>
  </header>
  {secs_html}
  <p class="no-result" id="lempty" hidden style="margin-top:28px">찾는 사이트가 없어요. 다른 단어로 검색해 보세요.</p>
  <p class="sec-desc" style="margin-top:36px">외부 사이트의 내용과 주소는 운영 기관 사정에 따라 바뀔 수 있어요.</p>
</main>"""
    head = breadcrumb_ld([("싸다구", ""), ("링크 모음", "links/")])
    return page("links/index.html", "링크 모음 · 싸다구", "식품 안전·가격 정보 공식 사이트, 레시피 사이트, 영양·살림 정보와 싸다구 만든 사람의 SNS 모음.",
                "links", body, notes, links, icons, extra_head=head, extra_js=LINKS_JS)


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
        ("장보기 노트는 누가 쓰나요?", "싸다구를 만든 사람이 장보기와 요리, 살림에 도움이 되는 내용을 정리해 올려요. 식품 안전처럼 중요한 정보는 제품 표시와 공식 기관의 안내를 우선으로 확인해 주세요."),
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
  <section class="sec" aria-labelledby="h-notes">
    <h2 class="sec-title" id="h-notes">장보기 노트 {len(notes)}편</h2>
    <p class="sec-desc">가격만 보는 게 아니라, 잘 사고 잘 먹는 법도 함께 정리해요</p>
    <div class="cat-grid">{cat_tiles(root, notes, with_desc=False)}</div>
  </section>
  <section class="sec" aria-labelledby="h-faq">
    <h2 class="sec-title" id="h-faq">자주 묻는 질문</h2>
    <p class="sec-desc">궁금한 게 더 있으면 SNS로 편하게 물어봐 주세요</p>
    <div class="faq">{faq_html}</div>
  </section>
  <section class="sec" aria-labelledby="h-maker">
    <h2 class="sec-title" id="h-maker">만든 사람</h2>
    <p class="sec-desc">{AUTHOR} · 개발하고, 기록하고, 가끔 장을 봐요</p>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <a class="btn" href="{root}links/">SNS와 사이트 보기</a>
      <a class="btn ghost" href="{root}tips/">장보기 노트 읽기</a>
    </div>
  </section>
</main>"""
    head = breadcrumb_ld([("싸다구", ""), ("소개", "about/")]) + ld({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq],
    })
    return page("about/index.html", "싸다구 소개 · 쌀 때 사다구", "싸다구가 쿠팡 가격을 기록하는 방법, 배지 읽는 법, 자주 묻는 질문.", "about", body, notes, links, icons, extra_head=head)


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
    head = page_head("페이지를 찾을 수 없어요 · 싸다구", "요청한 페이지를 찾을 수 없어요.", "404.html", SITE_BASE,
                     extra='<meta name="robots" content="noindex">\n')
    return head + header(SITE_BASE, "") + "\n" + body + "\n" + footer(SITE_BASE, notes, links, icons) + "\n" + SCROLL_JS + "\n</body>\n</html>\n"


def build_sitemap(notes):
    today = datetime.date.today().isoformat()
    urls = [("", today), ("tips/", today), ("about/", today), ("links/", today)]
    urls += [(f"tips/c/{v[0]}/", today) for v in CATS.values()]
    urls += [(f"tips/{n['slug']}/", n.get("updated", n["date"])) for n in notes]
    items = "".join(f"  <url><loc>{SITE_URL}{u}</loc><lastmod>{d}</lastmod></url>\n" for u, d in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}</urlset>\n'


def build_feed(notes):
    def rfc822(iso):
        d = datetime.datetime.strptime(iso, "%Y-%m-%d")
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"{days[d.weekday()]}, {d.day:02d} {months[d.month - 1]} {d.year} 09:00:00 +0900"
    items = "".join(f"""  <item>
    <title>{esc(n['title'])}</title>
    <link>{SITE_URL}tips/{n['slug']}/</link>
    <guid>{SITE_URL}tips/{n['slug']}/</guid>
    <category>{esc(n['category'])}</category>
    <pubDate>{rfc822(n['date'])}</pubDate>
    <description>{esc(n['description'])}</description>
  </item>
""" for n in sorted(notes, key=lambda x: x["order"]))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>싸다구 장보기 노트</title>
  <link>{SITE_URL}tips/</link>
  <description>쿠팡 싸게 사는 습관, 재료 고르는 법, 보관, 레시피, 살림 이야기</description>
  <language>ko</language>
{items}</channel>
</rss>
"""


def home_seo():
    return ld({
        "@context": "https://schema.org", "@type": "WebSite", "name": "싸다구", "alternateName": "쌀 때 사다구",
        "url": SITE_URL, "inLanguage": "ko-KR",
        "description": "자주 사는 쿠팡 상품 가격을 매일 기록하고, 쌀 때만 알려주는 개인 장보기 노트.",
        "potentialAction": {"@type": "SearchAction", "target": SITE_URL + "tips/?q={search_term_string}", "query-input": "required name=search_term_string"},
    }) + ld({
        "@context": "https://schema.org", "@type": "Organization", "name": "싸다구", "url": SITE_URL,
        "logo": SITE_URL + "apple-touch-icon.png",
        "sameAs": ["https://www.instagram.com/wait_secs/", "https://x.com/wait_secs", "https://www.threads.com/@wait_secs/", "https://github.com/daeseji"],
    }) + f'<link rel="canonical" href="{SITE_URL}">\n<link rel="alternate" type="application/rss+xml" title="싸다구 장보기 노트" href="{SITE_URL}tips/feed.xml">\n'


def update_index(notes, links, icons):
    path = ROOT / "index.html"
    s = path.read_text(encoding="utf-8")
    s = re.sub(r"<!-- @seo -->.*?<!-- /@seo -->", lambda m: "<!-- @seo -->\n" + home_seo() + "<!-- /@seo -->", s, flags=re.S)
    s = re.sub(r"<!-- @header -->.*?<!-- /@header -->", lambda m: "<!-- @header -->\n" + header("", "home") + "\n<!-- /@header -->", s, flags=re.S)
    s = re.sub(r"<!-- @footer -->.*?<!-- /@footer -->", lambda m: "<!-- @footer -->\n" + footer("", notes, links, icons) + "\n<!-- /@footer -->", s, flags=re.S)
    path.write_text(s, encoding="utf-8")


def write(rel, content):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def write_og_manifest(notes):
    items = [{"slug": n["slug"], "title": n["title"], "category": n["category"], "cat": n["cat"],
              "icon": NOTE_ICONS.get(n["icon"], NOTE_ICONS["tag"])} for n in notes]
    write("og/manifest.json", json.dumps(items, ensure_ascii=False, indent=1) + "\n")


def main():
    notes = sorted((parse_note(p) for p in (ROOT / "content/tips").glob("*.md")), key=lambda n: n["order"])
    slugs = [n["slug"] for n in notes]
    assert len(slugs) == len(set(slugs)), "노트 주소가 겹쳐요"
    bad = [n["slug"] for n in notes if n["category"] not in CATS or n["icon"] not in NOTE_ICONS]
    assert not bad, f"카테고리나 아이콘 이름을 확인하세요: {bad}"
    links = json.loads((ROOT / "content/links.json").read_text(encoding="utf-8"))
    icons = json.loads((ROOT / "content/brand-icons.json").read_text(encoding="utf-8"))
    write("tips/index.html", build_tips_index(notes, links, icons))
    for name in CATS:
        write(f"tips/c/{CATS[name][0]}/index.html", build_category(name, notes, links, icons))
    for n in notes:
        write(f"tips/{n['slug']}/index.html", build_note(n, notes, links, icons))
    write("tips/feed.xml", build_feed(notes))
    write("links/index.html", build_links(notes, links, icons))
    write("about/index.html", build_about(notes, links, icons))
    write("404.html", build_404(notes, links, icons))
    write("sitemap.xml", build_sitemap(notes))
    write_og_manifest(notes)
    update_index(notes, links, icons)
    with_og = sum(1 for n in notes if n["og"] != "og.png")
    counts = ", ".join(f"{k} {sum(1 for n in notes if n['category'] == k)}" for k in CATS)
    print(f"✓ 노트 {len(notes)}편 ({counts}) · 공유 이미지 {with_og}장 · 카테고리·링크·소개·404·사이트맵·RSS·index.html")


if __name__ == "__main__":
    main()
