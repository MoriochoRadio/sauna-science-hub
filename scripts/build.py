#!/usr/bin/env python3
"""
Sauna Science Hub — 빌드 타임 정적 사이트 생성기 (v2).

data/research.json 을 읽어 index.html 을 생성한다.
- 한국어/영문 토글, 정렬(최신/근거/임상), 근거 등급 필터, 실시간 카운트
- About(방법론) 패널, 상위 근거 하이라이트, 다크모드
- 브라우저 측 파싱 없이 완성된 정적 HTML 출력.
"""
import json
import html
import sys
from collections import Counter, OrderedDict
from datetime import date

DATA = "data/research.json"
OUT = "index.html"

CATEGORY_META = OrderedDict([
    ("심혈관", ("#c2410c", "심혈관 건강")),
    ("사망률·수명", ("#b45309", "사망률 · 수명")),
    ("인지·뇌", ("#7c3aed", "인지 · 뇌")),
    ("대사·체중", ("#0d9488", "대사 · 체중")),
    ("호흡기", ("#2563eb", "호흡기")),
    ("회복·운동", ("#db2777", "회복 · 운동")),
    ("정신건강", ("#16a34a", "정신건강")),
    ("통증·염증", ("#dc2626", "통증 · 염증")),
    ("기타", ("#64748b", "기타")),
])

EVIDENCE_RANK = {
    "무작위 대조 시험(RCT)": 1,
    "대조 임상시험": 2,
    "임상시험": 3,
    "임상시험 I상": 3, "임상시험 II상": 3, "임상시험 III상": 3, "임상시험 IV상": 3,
    "메타분석": 1, "체계적 문헌고찰": 2, "리뷰": 4,
    "코호트 연구": 3, "환자-대조 연구": 3, "관찰 연구": 4, "단면 연구": 4,
    "기타": 5,
}

EVIDENCE_GROUPS = OrderedDict([
    ("RCT", ["무작위 대조 시험(RCT)"]),
    ("임상시험", ["임상시험", "임상시험 I상", "임상시험 II상", "임상시험 III상", "임상시험 IV상", "대조 임상시험"]),
    ("메타·고찰", ["메타분석", "체계적 문헌고찰", "리뷰"]),
    ("관찰연구", ["코호트 연구", "환자-대조 연구", "관찰 연구", "단면 연구"]),
])


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# 주제별 색상 (차분한 톤 — AI 팔레트 지양)
_CAT_COLORS = {
    "심혈관": "#9a3b3b",
    "사망률·수명": "#5b6b8a",
    "인지·뇌": "#5a7d6b",
    "대사·체중": "#8a6a2e",
    "호흡기": "#4f7a86",
    "회복·운동": "#6b4f86",
    "정신건강": "#7a6a3a",
    "통증·염증": "#9a5a3a",
    "기타": "#6b665c",
}
def cat_color(cat):
    return _CAT_COLORS.get(cat, "#6b665c")


def ev_group(ev):
    for g, lst in EVIDENCE_GROUPS.items():
        if ev in lst:
            return g
    return "기타"


def load():
    try:
        with open(DATA, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[build] {DATA} 없음 — 빈 사이트 생성", file=sys.stderr)
        return {"updated": str(date.today()), "count": 0, "articles": []}


def card(a, idx):
    cats = a.get("categories", ["기타"])
    cat_html = "".join(
        f'<span class="tag" style="--c:{cat_color(c)}">{esc(c)}</span>'
        for c in cats
    )
    authors = a.get("authors", [])
    if authors:
        author_str = ", ".join(authors[:3]) + (f" 외 {len(authors)-3}명" if len(authors) > 3 else "")
    else:
        author_str = "저자 미상"
    meta_bits = []
    if a.get("journal"):
        meta_bits.append(esc(a["journal"]))
    if a.get("year"):
        meta_bits.append(esc(a["year"]))
    meta = " · ".join(meta_bits)
    evidence = a.get("evidence", "기타")
    rank = EVIDENCE_RANK.get(evidence, 5)
    group = ev_group(evidence)
    clinical = "1" if a.get("is_clinical") else "0"
    title_ko = esc(a.get("title_ko", ""))
    title_en = esc(a.get("title", ""))
    abs_ko = esc(a.get("abstract_ko", ""))
    abs_en = esc(a.get("abstract", ""))
    top_cls = ' top' if rank <= 1 else ""
    top = '<span class="topstar">★ 최고근거</span>' if rank <= 1 else ""
    cats_html = cat_html
    abs_ko_html = f'<span class="t-ko">{abs_ko}</span>' if abs_ko else ""
    abs_en_html = f'<span class="t-en">{abs_en}</span>' if abs_en else ""
    title_html = (
        f'<span class="t-ko t-main">{title_ko}</span>'
        f'<span class="t-en t-sub">{title_en}</span>' if title_ko
        else f'<span class="t-en t-main">{title_en}</span>'
    )
    year_disp = esc(a.get("year", "—"))
    src = esc(a.get("journal", "출처 미상"))
    data_text = esc((title_en + " " + title_ko + " " + abs_en + " " + abs_ko + " " +
                    src + " " + " ".join(authors)).lower())
    return f"""
    <article class="entry{top_cls}" data-year="{esc(a.get('year','0'))}" data-rank="{rank}" data-clinical="{clinical}" data-group="{group}" data-cats='{esc(json.dumps(cats, ensure_ascii=False))}' data-text="{data_text}">
      <div class="yr">{year_disp}<small>{esc(a.get('volume',''))}</small></div>
      <div class="body">
        <span class="ev">{esc(evidence)}</span><span class="rank">근거 {rank}급</span>{top}
        <h3><a href="{esc(a['url'])}" target="_blank" rel="noopener">{title_html}</a></h3>
        <div class="cats">{cats_html}</div>
        <p class="abs collapsed" id="abs-{esc(a.get('pmid',''))}">{abs_ko_html}{abs_en_html}</p>
        <div class="abs-toggle" data-target="abs-{esc(a.get('pmid',''))}">초록 { '펴기 ▲' if (abs_ko or abs_en) else '없음' }</div>
        <div class="meta"><span class="src">{src}</span> · {esc(author_str)} <a class="lk" href="{esc(a['url'])}" target="_blank" rel="noopener">PubMed →</a></div>
      </div>
    </article>"""


def build():
    data = load()
    articles = data.get("articles", [])
    updated = data.get("updated", str(date.today()))
    total = data.get("count", len(articles))
    clinical = data.get("clinical_count", sum(1 for a in articles if a.get("is_clinical")))

    cat_counts = Counter()
    for a in articles:
        for c in a.get("categories", ["기타"]):
            cat_counts[c] += 1
    group_counts = Counter(ev_group(a.get("evidence", "기타")) for a in articles)

    years = Counter(a.get("year", "") for a in articles if a.get("year"))
    year_stats = ", ".join(f"{y}년 {n}편" for y, n in sorted(years.items(), reverse=True)[:6])

    filter_btns = ['<button class="fbtn active" data-cat="all">전체 <span class="cnt">{total}</span></button>']
    for c in CATEGORY_META:
        if cat_counts.get(c):
            color = cat_color(c)
            filter_btns.append(
                f'<button class="fbtn" data-cat="{esc(c)}" style="--c:{color}">{esc(c)} <span class="cnt">{cat_counts[c]}</span></button>'
            )
    filter_html = "".join(filter_btns)

    ev_btns = ['<button class="fbtn ev active" data-group="all">전체 등급</button>']
    for g, _ in EVIDENCE_GROUPS.items():
        if group_counts.get(g):
            ev_btns.append(
                f'<button class="fbtn ev" data-group="{g}">{esc(g)} <span class="cnt">{group_counts[g]}</span></button>'
            )
    ev_html = "".join(ev_btns)

    cards_html = "\n".join(card(a, i) for i, a in enumerate(articles))

    html_doc = TEMPLATE
    html_doc = (html_doc
        .replace("__TITLE__", "사우나 사이언스 허브 — 증거 기반 사우나 연구 아카이브")
        .replace("__DESC__", esc("사우나의 과학적 근거: 심혈관, 사망률, 인지, 대사, 회복, 정신건강 등 PubMed 기반 peer-reviewed 연구 및 임상시험 한눈에 보기."))
        .replace("__TOTAL__", str(total))
        .replace("__CLINICAL__", str(clinical))
        .replace("__NCAT__", str(len(cat_counts)))
        .replace("__UPDATED__", esc(updated))
        .replace("__YEARSTATS__", esc(year_stats) or "—")
        .replace("__FILTERS__", filter_html)
        .replace("__EVIDENCE_FILTERS__", ev_html)
        .replace("__CARDS__", cards_html)
        .replace("__EMPTY_DISPLAY__", "block" if total == 0 else "none"))

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print(f"[build] index.html 생성 완료 ({len(articles)}편)", file=sys.stderr)


TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko" data-theme="light" data-lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:type" content="website">
<style>
:root{
  --paper:#f4f1ea; --panel:#ffffff; --ink:#1c1a15; --ink2:#57534a;
  --rule:#d6d0c2; --rule2:#e7e1d4; --accent:#6e5a1c; --accent2:#8a6a14;
  --cat:#6b665c; --mark:#f0e0a8; --shadow:0 1px 2px rgba(35,33,28,.06),0 6px 18px rgba(35,33,28,.05);
}
[data-theme="dark"]{
  --paper:#16140f; --panel:#1f1c16; --ink:#e9e3d6; --ink2:#9a9183;
  --rule:#332f27; --rule2:#27231d; --accent:#dc8f87; --accent2:#d3a85f;
  --cat:#948b7e; --mark:#574a1e; --shadow:0 1px 2px rgba(0,0,0,.45),0 6px 18px rgba(0,0,0,.35);
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:"Apple SD Gothic Neo","Malgun Gothic",-apple-system,"Segoe UI",sans-serif;background:var(--paper);color:var(--ink);line-height:1.6;-webkit-font-smoothing:antialiased;}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
a{color:inherit}

/* 좌측 정렬 마스트헤드 — 저널/편집자 톤 */
.masthead{border-bottom:3px double var(--rule);padding:40px 0 30px}
.mast-kicker{font:600 .72rem/1 "Courier New",monospace;letter-spacing:.18em;text-transform:uppercase;color:var(--accent2)}
.mast h1{font-size:clamp(2.1rem,5vw,3rem);font-weight:800;letter-spacing:-.02em;line-height:1.08;margin:12px 0 10px}
.mast .dek{max-width:640px;color:var(--ink2);font-size:1.02rem}
.mast-meta{display:flex;flex-wrap:wrap;gap:0;margin-top:22px;border-top:1px solid var(--rule2)}
.mast-meta div{flex:1 1 120px;padding:12px 14px 12px 0;border-right:1px solid var(--rule2)}
.mast-meta div:last-child{border-right:0}
.mast-meta b{display:block;font-size:1.5rem;font-weight:800;color:var(--accent);line-height:1}
.mast-meta span{font-size:.74rem;color:var(--ink2);letter-spacing:.02em}
.issue{font:600 .7rem/1 "Courier New",monospace;letter-spacing:.1em;color:var(--ink2);text-transform:uppercase;margin-top:18px}

/* 컨트롤 바 */
.bar{position:sticky;top:0;z-index:20;background:var(--paper);border-bottom:1px solid var(--rule);padding:12px 0}
.search{width:100%;padding:11px 14px;border:1px solid var(--rule);border-radius:0;background:var(--panel);color:var(--ink);font:inherit;font-size:.95rem}
.search:focus{outline:2px solid var(--accent);outline-offset:-1px}
.bar2{display:flex;gap:10px;margin-top:10px;align-items:center;flex-wrap:wrap}
.filters{display:flex;flex-wrap:wrap;gap:0}
.fbtn{font:inherit;font-size:.82rem;cursor:pointer;border:1px solid var(--rule);border-right-width:0;background:var(--panel);color:var(--ink);padding:6px 12px;transition:.12s;border-left:3px solid var(--c,transparent)}
.filters .fbtn:first-child{border-top-left-radius:4px;border-bottom-left-radius:4px}
.filters .fbtn:last-of-type{border-right-width:1px;border-top-right-radius:4px;border-bottom-right-radius:4px}
.fbtn:hover{border-color:var(--accent)}
.fbtn.active{background:var(--accent);border-color:var(--accent);color:#fff;border-left-color:var(--c,var(--accent))}
.fbtn .cnt{opacity:.65;font-size:.74rem;margin-left:3px}
.fbtn.ev.active{background:var(--accent2);border-color:var(--accent2)}
.spacer{flex:1}
.txtbtn{cursor:pointer;border:1px solid var(--rule);background:var(--panel);color:var(--ink);border-radius:4px;padding:6px 13px;font:inherit;font-size:.82rem}
.txtbtn:hover{border-color:var(--accent)}
select.sort{font:inherit;font-size:.82rem;border:1px solid var(--rule);background:var(--panel);color:var(--ink);border-radius:4px;padding:6px 10px;cursor:pointer}
.countbar{font-size:.82rem;color:var(--ink2);margin-top:10px}
.countbar b{color:var(--accent);font-weight:800}
.countbar .reset{cursor:pointer;color:var(--accent2);text-decoration:underline;margin-left:8px}

/* 방법론 노트 */
.note{border:1px solid var(--rule);border-left:3px solid var(--accent2);background:var(--panel);padding:14px 18px;margin-top:16px;font-size:.88rem;color:var(--ink2)}
.note summary{cursor:pointer;font-weight:700;color:var(--ink);font-size:.95rem}
.note ul{margin:10px 0 0 18px}
.note li{margin:4px 0}

/* 리스트 레이아웃 (카드 아님) */
main{padding:24px 0 60px}
.grid{display:flex;flex-direction:column}
.entry{border-top:1px solid var(--rule);padding:18px 0;display:grid;grid-template-columns:72px 1fr;gap:18px;transition:background .12s}
.entry:hover{background:var(--panel)}
.entry:first-child{border-top:0}
.entry.top{background:linear-gradient(90deg,rgba(110,90,28,.06),transparent 60%);border-left:3px solid var(--accent);padding-left:14px;margin-left:-17px}
.entry .yr{font:700 1.05rem/1.1 "Courier New",monospace;color:var(--accent);text-align:right;padding-top:2px}
.entry .yr small{display:block;font-size:.62rem;color:var(--ink2);font-weight:400;letter-spacing:.05em;margin-top:3px}
.entry .body{min-width:0}
.ev{display:inline-block;font-size:.68rem;font-weight:700;letter-spacing:.03em;border:1px solid var(--rule);padding:1px 7px;color:var(--accent2);margin-bottom:6px}
.rank{font-size:.66rem;color:var(--ink2);margin-left:6px}
.topstar{color:var(--accent);font-weight:800;margin-left:6px}
.entry h3{font-size:1.08rem;font-weight:700;line-height:1.34;letter-spacing:-.01em}
.entry h3 a{text-decoration:none}
.entry h3 a:hover{color:var(--accent);text-decoration:underline}
.t-en.t-sub{display:block;font-weight:400;font-size:.82rem;color:var(--ink2);margin-top:3px;line-height:1.35}
.cats{display:flex;flex-wrap:wrap;gap:5px;margin:8px 0}
.tag{font-size:.7rem;color:#fff;background:var(--cat);padding:2px 8px;letter-spacing:.02em}
.abs{font-size:.9rem;color:var(--ink2);line-height:1.7;margin-top:6px}
.abs.collapsed{max-height:3.4em;overflow:hidden;position:relative}
.abs .t-en{display:none}
.abs-toggle{cursor:pointer;font-size:.76rem;color:var(--accent2);font-weight:700;margin-top:6px;user-select:none}
.abs-toggle:hover{text-decoration:underline}
.meta{font-size:.78rem;color:var(--ink2);margin-top:8px}
.meta .src{color:var(--accent);font-weight:600}
.lk{font-size:.78rem;font-weight:700;color:var(--accent2);text-decoration:none;margin-left:10px}
.lk:hover{text-decoration:underline}
mark{background:var(--mark);color:inherit;padding:0 1px}

[data-theme="dark"] .entry .yr{color:var(--accent)}
[data-theme="dark"] .fbtn.active{color:#16140f}
[data-theme="dark"] .fbtn.ev.active{color:#16140f}

.totop{position:fixed;right:18px;bottom:18px;width:40px;height:40px;border:1px solid var(--rule);background:var(--panel);color:var(--ink);font-size:1.1rem;cursor:pointer;display:none;z-index:30}
.nores{text-align:center;padding:40px;color:var(--ink2);display:none}
@media(max-width:620px){
  .entry{grid-template-columns:1fr;gap:6px;padding:26px 0}
  .entry .yr{text-align:left;font-size:.9rem}
  .entry .yr small{display:inline;margin:0 0 0 6px}
  .mast-meta div{flex-basis:50%}
  .masthead{padding:30px 0 22px}
  .mast h1{font-size:1.9rem}
  .mast-kicker{font-size:.66rem}
  .bar{padding:14px 0}
  .bar2{gap:8px}
}
</style>
</head>
<body>
<header class="masthead">
  <div class="wrap mast">
    <div class="mast-kicker">Evidence-Based Sauna Research Archive</div>
    <h1>사우나 사이언스 허브</h1>
    <p class="dek">사우나가 인체에 미치는 과학적 근거를 모았다. PubMed에서 매일 자동 수집되는 peer-reviewed 연구와 임상시험을 주제·근거 수준별로 정리했다. 제목과 초록은 기계번역 한국어와 원문을 함께 읽는다.</p>
    <div class="mast-meta">
      <div><b>__TOTAL__</b><span>수집 논문</span></div>
      <div><b>__CLINICAL__</b><span>임상시험 · RCT</span></div>
      <div><b>__NCAT__</b><span>주제 분류</span></div>
      <div><b>__UPDATED__</b><span>최종 갱신</span></div>
    </div>
    <div class="issue">정기 간행물 형태 · 매일 KST 10:17 자동 발행</div>
  </div>
</header>

<div class="bar">
  <div class="wrap">
    <input id="search" class="search" type="search" placeholder="논문 검색 — 제목·초록·저널·저자 (예: blood pressure, 치매, 회복)" aria-label="검색">
    <div class="bar2">
      <div class="filters" id="catFilters">__FILTERS__</div>
      <div class="spacer"></div>
      <select class="sort" id="sort" aria-label="정렬">
        <option value="latest">최신순</option>
        <option value="evidence">근거 수준순</option>
        <option value="clinical">임상시험 우선</option>
      </select>
      <button class="txtbtn" id="lang">원문 보기</button>
      <button class="txtbtn" id="dark">다크모드</button>
    </div>
    <div class="bar2">
      <div class="filters" id="evFilters">__EVIDENCE_FILTERS__</div>
    </div>
    <div class="countbar">표시 <b id="shown">__TOTAL__</b> / __TOTAL__편<span class="reset" id="reset" style="display:none">필터 초기화</span></div>
  </div>
</div>

<div class="wrap">
  <details class="note">
    <summary>이 아카이브는 어떻게 만들어졌나 (방법론)</summary>
    <ul>
      <li><b>출처</b>: <a href="https://pubmed.ncbi.nlm.nih.gov/" target="_blank" rel="noopener">PubMed</a>(NCBI)의 peer-reviewed 논문 메타데이터. 키 없이 무료 E-utilities로 매일 수집한다.</li>
      <li><b>근거 수준</b>: 출판 유형별로 RCT·임상시험·메타분석·코호트 등을 라벨링하고 1~5급으로 표시(1급=가장 높은 근거). <b>★</b> 표시는 1급(RCT·메타분석)이다.</li>
      <li><b>번역</b>: 제목·초록은 기계번역으로 한국어를 제공한다(원문 토글 가능). 번역 품질은 참고용이며 정확한 내용은 원문 링크를 확인하라.</li>
      <li><b>주제 분류</b>: 초록 키워드 기반 자동 태깅(심혈관·사망률·인지·대사·호흡기·회복·정신건강·통증·염증).</li>
      <li><b>면책</b>: 교육·정보 목적이며 의학적 조언을 대체하지 않는다. 사우나 이용은 건강 상태에 따라 전문의와 상담하라.</li>
    </ul>
  </details>
</div>

<main>
  <div class="wrap">
    <div class="grid" id="grid">
__CARDS__
    </div>
    <div class="nores" id="nores">검색·필터 결과가 없습니다.</div>
    <p style="color:var(--ink2);font-size:.78rem;margin-top:22px;border-top:1px solid var(--rule2);padding-top:14px;">연도별 분포: __YEARSTATS__</p>
  </div>
</main>

<button class="totop" id="totop" aria-label="맨 위로">↑</button>

<footer>
  <div class="wrap">
    <p>사우나 사이언스 허브 · <a href="https://pubmed.ncbi.nlm.nih.gov/" target="_blank" rel="noopener">PubMed</a> 기반 무료 키없는 자동 수집. 모든 항목은 원논문(PubMed)으로 연결된다.</p>
    <p style="margin-top:6px;">본 아카이브는 교육·정보 목적이며 의학적 조언을 대체하지 않는다.</p>
  </div>
</footer>

<script>
(function() {
  var grid = document.getElementById('grid');
  var cards = Array.prototype.slice.call(grid.querySelectorAll('.entry'));
  var search = document.getElementById('search');
  var nores = document.getElementById('nores');
  var shownEl = document.getElementById('shown');
  var sortSel = document.getElementById('sort');
  var resetBtn = document.getElementById('reset');
  var activeCat = 'all', activeGroup = 'all';
  function norm(s){ return (s||'').toLowerCase(); }
  function toInt(v){ var n=parseInt(v,10); return isNaN(n)?0:n; }

  function apply() {
    var q = norm(search.value).trim();
    var list = cards.filter(function(c){
      var raw = (c.getAttribute('data-cats')||'[]').replace(/&quot;/g,'"');
      var cats; try { cats = JSON.parse(raw); } catch(e){ cats = []; }
      var catOk = activeCat==='all' || cats.indexOf(activeCat)!==-1;
      var grpOk = activeGroup==='all' || c.getAttribute('data-group')===activeGroup;
      var txt = norm(c.getAttribute('data-text'));
      var match = !q || txt.indexOf(q)!==-1;
      return catOk && grpOk && match;
    });
    var mode = sortSel.value;
    list.sort(function(a,b){
      if(mode==='evidence'){ var r=toInt(a.getAttribute('data-rank'))-toInt(b.getAttribute('data-rank')); return r!==0?r:toInt(b.getAttribute('data-year'))-toInt(a.getAttribute('data-year')); }
      if(mode==='clinical'){ var c=toInt(b.getAttribute('data-clinical'))-toInt(a.getAttribute('data-clinical')); return c!==0?c:toInt(b.getAttribute('data-year'))-toInt(a.getAttribute('data-year')); }
      return toInt(b.getAttribute('data-year'))-toInt(a.getAttribute('data-year'));
    });
    cards.forEach(function(c){ c.style.display='none'; clearHL(c); });
    list.forEach(function(c){ c.style.display=''; grid.appendChild(c); if(q) highlight(c,q); });
    shownEl.textContent = list.length;
    nores.style.display = list.length===0 ? 'block' : 'none';
    resetBtn.style.display = (activeCat!=='all' || activeGroup!=='all' || q) ? 'inline' : 'none';
    syncURL(q);
  }

  // 현재 필터/검색을 URL 쿼리에 반영 (공유용)
  function syncURL(q){
    try {
      var p = new URLSearchParams();
      if(q) p.set('q', q);
      if(activeCat!=='all') p.set('cat', activeCat);
      if(activeGroup!=='all') p.set('grp', activeGroup);
      if(sortSel.value!=='latest') p.set('sort', sortSel.value);
      var s = p.toString();
      history.replaceState(null, '', s ? (location.pathname+'?'+s) : location.pathname);
    } catch(e){}
  }

  function escapeRe(s){ return s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'); }
  function highlight(card, q){
    card.querySelectorAll('h3 a, .abs').forEach(function(node){
      try {
        var re = new RegExp('('+escapeRe(q)+')','gi');
        node.innerHTML = node.innerHTML.replace(re, '<mark>$1</mark>');
      } catch(e){}
    });
  }
  function clearHL(card){
    card.querySelectorAll('mark').forEach(function(m){
      var p=m.parentNode; if(!p) return;
      p.replaceChild(document.createTextNode(m.textContent), m); p.normalize();
    });
  }

  search.addEventListener('input', apply);
  sortSel.addEventListener('change', apply);
  function bindFilters(sel, attr, cb){
    document.querySelectorAll(sel).forEach(function(b){
      b.addEventListener('click', function(){
        document.querySelectorAll(sel).forEach(function(x){ x.classList.remove('active'); });
        b.classList.add('active');
        cb(b.getAttribute(attr)); apply();
      });
    });
  }
  bindFilters('#catFilters .fbtn', 'data-cat', function(v){ activeCat=v; });
  bindFilters('#evFilters .fbtn', 'data-group', function(v){ activeGroup=v; });
  resetBtn.addEventListener('click', function(){
    activeCat='all'; activeGroup='all'; search.value='';
    document.querySelectorAll('.fbtn').forEach(function(x){ x.classList.remove('active'); });
    document.querySelector('#catFilters .fbtn').classList.add('active');
    document.querySelector('#evFilters .fbtn').classList.add('active');
    apply();
  });

  // 공유 링크 복원: URL 쿼리에서 필터/검색/정렬 적용
  try {
    var u = new URLSearchParams(location.search);
    if(u.get('q')){ search.value = u.get('q'); }
    if(u.get('cat')){
      var cb = document.querySelector('#catFilters .fbtn[data-cat="'+u.get('cat')+'"]');
      if(cb){ document.querySelectorAll('#catFilters .fbtn').forEach(function(x){x.classList.remove('active');}); cb.classList.add('active'); activeCat=u.get('cat'); }
    }
    if(u.get('grp')){
      var gb = document.querySelector('#evFilters .fbtn[data-group="'+u.get('grp')+'"]');
      if(gb){ document.querySelectorAll('#evFilters .fbtn').forEach(function(x){x.classList.remove('active');}); gb.classList.add('active'); activeGroup=u.get('grp'); }
    }
    if(u.get('sort')){ sortSel.value=u.get('sort'); }
  } catch(e){}

  // 언어 토글 (한국어 <-> 원문)
  var langBtn = document.getElementById('lang');
  var savedLang = localStorage.getItem('ssh-lang') || 'ko';
  setLang(savedLang);
  langBtn.addEventListener('click', function(){
    var cur = document.documentElement.getAttribute('data-lang');
    setLang(cur==='ko' ? 'en' : 'ko');
  });
  function setLang(l){
    document.documentElement.setAttribute('data-lang', l);
    langBtn.textContent = l==='ko' ? '원문 보기' : '한국어 보기';
    localStorage.setItem('ssh-lang', l);
  }

  // 다크모드
  var btn = document.getElementById('dark');
  var saved = localStorage.getItem('ssh-theme');
  if(saved==='dark') setDark(true);
  btn.addEventListener('click', function(){ setDark(document.documentElement.getAttribute('data-theme')==='dark' ? false : true); });
  function setDark(on){ document.documentElement.setAttribute('data-theme', on?'dark':'light'); btn.textContent = on?'라이트모드':'다크모드'; localStorage.setItem('ssh-theme', on?'dark':'light'); }

  // 맨 위로
  var top = document.getElementById('totop');
  window.addEventListener('scroll', function(){ top.style.display = window.scrollY>500?'block':'none'; });
  top.addEventListener('click', function(){ window.scrollTo({top:0,behavior:'smooth'}); });

  // 초록 펼침/접힘 토글
  document.querySelectorAll('.abs-toggle').forEach(function(t){
    if(t.textContent.indexOf('없음')!==-1) return;
    t.addEventListener('click', function(){
      var el = document.getElementById(t.getAttribute('data-target'));
      if(!el) return;
      var open = el.classList.toggle('collapsed') === false;
      t.textContent = open ? '초록 닫기 ▼' : '초록 펼치기 ▲';
    });
  });

  apply();
})();
</script>
</body>
</html>"""


if __name__ == "__main__":
    build()
