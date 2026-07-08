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
    return html.escape(str(s or ""), quote=True)


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
        f'<span class="tag" style="--c:{CATEGORY_META.get(c, CATEGORY_META["기타"])[0]}">{esc(c)}</span>'
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
    top = '<span class="top-badge">★ 최고 근거</span>' if rank <= 1 else ""
    abs_ko_html = f'<span class="t-ko">{abs_ko}</span>' if abs_ko else ""
    abs_en_html = f'<span class="t-en">{abs_en}</span>' if abs_en else ""
    # 제목: 한글(주), 영문(보조). 영문 모드에선 반전.
    title_html = (
        f'<span class="t-ko t-main">{title_ko}</span>'
        f'<span class="t-en t-sub">{title_en}</span>' if title_ko
        else f'<span class="t-en t-main">{title_en}</span>'
    )
    data_text = esc((title_en + " " + title_ko + " " + abs_en + " " + abs_ko + " " +
                    a.get("journal", "") + " " + " ".join(authors)).lower())
    return f"""
    <article class="card" data-year="{esc(a.get('year','0'))}" data-rank="{rank}" data-clinical="{clinical}" data-group="{group}" data-cats='{esc(json.dumps(cats, ensure_ascii=False))}' data-text="{data_text}">
      <div class="card-top">
        <span class="evi">{esc(evidence)}</span>
        <span class="evi-rank">근거 {rank}급</span>
        {top}
      </div>
      <h3><a href="{esc(a['url'])}" target="_blank" rel="noopener">{title_html}</a></h3>
      <div class="cats">{cat_html}</div>
      <p class="abs">{abs_ko_html}{abs_en_html}</p>
      <div class="meta">{meta} · {esc(author_str)}</div>
      <a class="link" href="{esc(a['url'])}" target="_blank" rel="noopener">PubMed에서 전문 보기 →</a>
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
            color = CATEGORY_META[c][0]
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@600;700&family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root { --bg:#faf7f2; --bg2:#f3ede3; --ink:#1f1b16; --muted:#6b6258; --line:#e6ddcf; --accent:#b45309; --accent2:#c2410c; --card:#ffffff; --shadow:0 1px 3px rgba(60,40,20,.08),0 8px 24px rgba(60,40,20,.06); --top:#b45309; }
[data-theme="dark"] { --bg:#15120e; --bg2:#1e1a14; --ink:#f1e9dd; --muted:#a99e8d; --line:#332c22; --accent:#e0913a; --accent2:#f2743d; --card:#211c15; --shadow:0 1px 3px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.35); --top:#e0913a; }
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:'Noto Sans KR',system-ui,sans-serif; background:var(--bg); color:var(--ink); line-height:1.65; -webkit-font-smoothing:antialiased; }
.wrap { max-width:1100px; margin:0 auto; padding:0 22px; }
header.hero { background:linear-gradient(160deg,var(--bg2),var(--bg)); border-bottom:1px solid var(--line); padding:54px 0 38px; }
.kicker { font-size:.8rem; letter-spacing:.22em; text-transform:uppercase; color:var(--accent); font-weight:700; }
h1 { font-family:'Noto Serif KR',serif; font-size:clamp(2rem,5vw,3.1rem); line-height:1.15; margin:10px 0 14px; font-weight:700; }
.lede { max-width:660px; color:var(--muted); font-size:1.05rem; }
.stats { display:flex; flex-wrap:wrap; gap:14px; margin-top:26px; }
.stat { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:14px 20px; box-shadow:var(--shadow); min-width:96px; }
.stat b { display:block; font-family:'Noto Serif KR',serif; font-size:1.7rem; color:var(--accent2); line-height:1; }
.stat span { font-size:.8rem; color:var(--muted); }
.toolbar { position:sticky; top:0; z-index:20; background:var(--bg); border-bottom:1px solid var(--line); padding:14px 0; backdrop-filter:saturate(1.2) blur(6px); }
.search { width:100%; padding:12px 16px; border:1px solid var(--line); border-radius:12px; background:var(--card); color:var(--ink); font-size:1rem; font-family:inherit; }
.search:focus { outline:2px solid var(--accent); outline-offset:1px; }
.row2 { display:flex; gap:10px; margin-top:12px; align-items:center; flex-wrap:wrap; }
.filters { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.fbtn { font-family:inherit; font-size:.85rem; cursor:pointer; border:1px solid var(--line); background:var(--card); color:var(--ink); padding:6px 13px; border-radius:999px; transition:.15s; }
.fbtn:hover { border-color:var(--accent); }
.fbtn.active { background:var(--accent); border-color:var(--accent); color:#fff; }
.fbtn .cnt { opacity:.7; font-size:.78rem; margin-left:2px; }
.fbtn.ev.active { background:var(--accent2); border-color:var(--accent2); }
.spacer { flex:1; }
.darktoggle,.langtoggle { cursor:pointer; border:1px solid var(--line); background:var(--card); color:var(--ink); border-radius:999px; padding:6px 14px; font-size:.85rem; font-family:inherit; }
select.sort { font-family:inherit; font-size:.85rem; border:1px solid var(--line); background:var(--card); color:var(--ink); border-radius:10px; padding:7px 12px; cursor:pointer; }
.countbar { font-size:.85rem; color:var(--muted); margin-top:12px; }
.countbar b { color:var(--accent2); }
.about { background:var(--bg2); border:1px solid var(--line); border-radius:14px; padding:18px 22px; margin-top:18px; }
.about summary { cursor:pointer; font-weight:700; font-family:'Noto Serif KR',serif; font-size:1.05rem; }
.about ul { margin:12px 0 0 18px; color:var(--muted); font-size:.9rem; }
.about li { margin:5px 0; }
main { padding:26px 0 70px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:18px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:20px; box-shadow:var(--shadow); display:flex; flex-direction:column; gap:10px; transition:.18s; border-left:4px solid var(--accent); }
.card:hover { transform:translateY(-3px); box-shadow:0 4px 10px rgba(60,40,20,.1),0 16px 36px rgba(60,40,20,.1); }
.card-top { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.evi { font-size:.74rem; font-weight:700; background:var(--bg2); color:var(--accent); padding:3px 9px; border-radius:999px; border:1px solid var(--line); }
.evi-rank { font-size:.72rem; color:var(--muted); }
.top-badge { font-size:.7rem; font-weight:700; color:var(--top); margin-left:auto; }
.card h3 { font-family:'Noto Serif KR',serif; font-size:1.12rem; line-height:1.35; font-weight:600; }
.card h3 a { color:var(--ink); text-decoration:none; }
.card h3 a:hover { color:var(--accent); text-decoration:underline; }
.cats { display:flex; flex-wrap:wrap; gap:6px; }
.tag { font-size:.72rem; color:#fff; background:var(--c,#64748b); padding:2px 9px; border-radius:999px; font-weight:500; }
.abs { font-size:.88rem; color:var(--muted); display:-webkit-box; -webkit-line-clamp:5; -webkit-box-orient:vertical; overflow:hidden; }
.abs .t-en { display:none; }
.meta { font-size:.8rem; color:var(--muted); margin-top:auto; }
.link { font-size:.82rem; font-weight:600; color:var(--accent2); text-decoration:none; }
.link:hover { text-decoration:underline; }
/* 영문 모드 */
body[data-lang="en"] .t-ko { display:none; }
body[data-lang="en"] .abs .t-en { display:block; }
body[data-lang="ko"] .t-en { display:none; }
body[data-lang="ko"] .abs .t-ko { display:block; }
/* 제목 보조 텍스트: 한글 모드에선 영문이 보조, 영문 모드에선 한글이 보조 */
body[data-lang="ko"] .t-sub { display:block; font-size:.82rem; font-weight:400; color:var(--muted); margin-top:4px; line-height:1.3; font-family:'Noto Sans KR',sans-serif; }
body[data-lang="en"] .t-sub { display:block; font-size:.82rem; font-weight:400; color:var(--muted); margin-top:4px; line-height:1.3; }
body[data-lang="ko"] .t-main, body[data-lang="en"] .t-main { font-family:'Noto Serif KR',serif; }
.empty { text-align:center; padding:80px 20px; color:var(--muted); }
.nores { text-align:center; padding:40px; color:var(--muted); display:none; }
footer { border-top:1px solid var(--line); background:var(--bg2); padding:30px 0; color:var(--muted); font-size:.85rem; }
footer a { color:var(--accent); }
.totop { position:fixed; right:20px; bottom:20px; width:44px; height:44px; border-radius:50%; border:1px solid var(--line); background:var(--card); color:var(--accent); font-size:1.2rem; cursor:pointer; box-shadow:var(--shadow); display:none; z-index:30; }
@media (max-width:560px) { .grid { grid-template-columns:1fr; } h1 { font-size:2rem; } .spacer { display:none; } }
</style>
</head>
<body>
<header class="hero">
  <div class="wrap">
    <div class="kicker">Evidence-Based Sauna Research</div>
    <h1>사우나 사이언스 허브</h1>
    <p class="lede">사우나가 몸에 미치는 과학적 근거를 한곳에서. PubMed에서 매일 자동 수집되는 peer-reviewed 연구·임상시험 아카이브. 제목·요약은 한국어 번역과 원문을 함께 제공합니다.</p>
    <div class="stats">
      <div class="stat"><b>__TOTAL__</b><span>수집 논문</span></div>
      <div class="stat"><b>__CLINICAL__</b><span>임상시험 · RCT</span></div>
      <div class="stat"><b>__NCAT__</b><span>주제 분류</span></div>
      <div class="stat"><b>__UPDATED__</b><span>최종 업데이트</span></div>
    </div>
  </div>
</header>

<div class="toolbar">
  <div class="wrap">
    <input id="search" class="search" type="search" placeholder="논문 제목·요약·저널 검색… (예: blood pressure, 치매, 회복)" aria-label="검색">
    <div class="row2">
      <div class="filters" id="catFilters">__FILTERS__</div>
      <div class="spacer"></div>
      <select class="sort" id="sort" aria-label="정렬">
        <option value="latest">최신순</option>
        <option value="evidence">근거 높은순</option>
        <option value="clinical">임상 우선</option>
      </select>
      <button class="langtoggle" id="lang">🌐 원문(EN)</button>
      <button class="darktoggle" id="dark">🌙 다크</button>
    </div>
    <div class="row2">
      <div class="filters" id="evFilters">__EVIDENCE_FILTERS__</div>
    </div>
    <div class="countbar">표시 중: <b id="shown">__TOTAL__</b> / __TOTAL__편</div>
  </div>
</div>

<div class="wrap">
  <details class="about">
    <summary>ℹ️ 이 사이트는 어떻게 만들어졌나요? (방법론)</summary>
    <ul>
      <li><b>출처</b>: <a href="https://pubmed.ncbi.nlm.nih.gov/" target="_blank" rel="noopener">PubMed</a>(NCBI)의 peer-reviewed 논문 메타데이터. 키 없이 무료 E-utilities로 매일 수집합니다.</li>
      <li><b>근거 등급</b>: 출판 유형에 따라 RCT·임상시험·메타분석·코호트 등을 라벨링하고 1~5급으로 표시(1급=가장 높은 근거). '★ 최고 근거'는 1급(RCT·메타분석)입니다.</li>
      <li><b>번역</b>: 제목·초록은 키없는 기계번역으로 한국어 제공(원문 토글 가능). 번역 품질은 참고용이며 정확한 내용은 원문 링크를 확인하세요.</li>
      <li><b>주제 분류</b>: 초록 키워드 기반 자동 태깅(심혈관·사망률·인지·대사·호흡기·회복·정신건강·통증·염증).</li>
      <li><b>자동화</b>: GitHub Actions가 매일 갱신하며, 빌드 타임에 정적 HTML로 렌더링됩니다.</li>
      <li><b>면책</b>: 교육·정보 목적이며 의학적 조언을 대체하지 않습니다. 사우나 이용은 건강 상태에 따라 전문의와 상담하세요.</li>
    </ul>
  </details>
</div>

<main>
  <div class="wrap">
    <div class="grid" id="grid">
__CARDS__
    </div>
    <div class="nores" id="nores">검색/필터 결과가 없습니다.</div>
    <p class="empty" style="display:__EMPTY_DISPLAY__">아직 수집된 자료가 없습니다. 곧 자동 업데이트됩니다.</p>
    <p style="color:var(--muted);font-size:.8rem;margin-top:24px;">연도별 분포: __YEARSTATS__</p>
  </div>
</main>

<button class="totop" id="totop" aria-label="맨 위로">↑</button>

<footer>
  <div class="wrap">
    <p>사우나 사이언스 허브 · <a href="https://pubmed.ncbi.nlm.nih.gov/" target="_blank" rel="noopener">PubMed</a> 기반 무료 키없는 자동 수집 · 모든 자료는 원 논문(PubMed)으로 연결됩니다.</p>
    <p style="margin-top:6px;">본 사이트는 교육·정보 목적이며 의학적 조언을 대체하지 않습니다.</p>
  </div>
</footer>

<script>
(function() {
  var grid = document.getElementById('grid');
  var cards = Array.prototype.slice.call(grid.querySelectorAll('.card'));
  var search = document.getElementById('search');
  var nores = document.getElementById('nores');
  var shownEl = document.getElementById('shown');
  var sortSel = document.getElementById('sort');
  var activeCat = 'all', activeGroup = 'all';
  function norm(s){ return (s||'').toLowerCase(); }
  function toInt(v){ var n=parseInt(v,10); return isNaN(n)?0:n; }

  function apply() {
    var q = norm(search.value).trim();
    var list = cards.filter(function(c){
      var cats = JSON.parse((c.getAttribute('data-cats')||'[]').replace(/&quot;/g,'"'));
      var catOk = activeCat==='all' || cats.indexOf(activeCat)!==-1;
      var grpOk = activeGroup==='all' || c.getAttribute('data-group')===activeGroup;
      var txt = norm(c.getAttribute('data-text'));
      var match = !q || txt.indexOf(q)!==-1;
      return catOk && grpOk && match;
    });
    // 정렬
    var mode = sortSel.value;
    list.sort(function(a,b){
      if(mode==='evidence'){ var r=toInt(a.getAttribute('data-rank'))-toInt(b.getAttribute('data-rank')); return r!==0?r:toInt(b.getAttribute('data-year'))-toInt(a.getAttribute('data-year')); }
      if(mode==='clinical'){ var c=toInt(b.getAttribute('data-clinical'))-toInt(a.getAttribute('data-clinical')); return c!==0?c:toInt(b.getAttribute('data-year'))-toInt(a.getAttribute('data-year')); }
      return toInt(b.getAttribute('data-year'))-toInt(a.getAttribute('data-year'));
    });
    // DOM 재배치
    cards.forEach(function(c){ c.style.display='none'; clearHL(c); });
    list.forEach(function(c){ c.style.display=''; grid.appendChild(c); if(q) highlight(c,q); });
    shownEl.textContent = list.length;
    nores.style.display = list.length===0 ? 'block' : 'none';
  }

  function highlight(card, q){
    card.querySelectorAll('h3 a, .abs').forEach(function(node){
      try{ var re=new RegExp('('+q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','gi'); node.innerHTML=node.innerHTML.replace(re,'<mark>$1</mark>'); }catch(e){}
    });
  }
  function clearHL(card){
    card.querySelectorAll('mark').forEach(function(m){ var p=m.parentNode; if(!p) return; p.replaceChild(document.createTextNode(m.textContent),m); p.normalize(); });
  }

  search.addEventListener('input', apply);
  sortSel.addEventListener('change', apply);
  document.querySelectorAll('#catFilters .fbtn').forEach(function(b){
    b.addEventListener('click', function(){ document.querySelectorAll('#catFilters .fbtn').forEach(function(x){x.classList.remove('active');}); b.classList.add('active'); activeCat=b.getAttribute('data-cat'); apply(); });
  });
  document.querySelectorAll('#evFilters .fbtn').forEach(function(b){
    b.addEventListener('click', function(){ document.querySelectorAll('#evFilters .fbtn').forEach(function(x){x.classList.remove('active');}); b.classList.add('active'); activeGroup=b.getAttribute('data-group'); apply(); });
  });

  // 언어 토글 (한국어 <-> 원문)
  var langBtn = document.getElementById('lang');
  var savedLang = localStorage.getItem('ssh-lang') || 'ko';
  setLang(savedLang);
  langBtn.addEventListener('click', function(){ var cur=document.documentElement.getAttribute('data-lang'); setLang(cur==='ko'?'en':'ko'); });
  function setLang(l){ document.documentElement.setAttribute('data-lang', l); langBtn.textContent = l==='ko' ? '🌐 원문(EN)' : '🌐 한국어'; localStorage.setItem('ssh-lang', l); }

  // 다크모드
  var btn = document.getElementById('dark');
  var saved = localStorage.getItem('ssh-theme');
  if(saved==='dark') setDark(true);
  btn.addEventListener('click', function(){ setDark(document.documentElement.getAttribute('data-theme')==='dark' ? false : true); });
  function setDark(on){ document.documentElement.setAttribute('data-theme', on?'dark':'light'); btn.textContent = on?'☀️ 라이트':'🌙 다크'; localStorage.setItem('ssh-theme', on?'dark':'light'); }

  // 맨 위로
  var top = document.getElementById('totop');
  window.addEventListener('scroll', function(){ top.style.display = window.scrollY>500?'block':'none'; });
  top.addEventListener('click', function(){ window.scrollTo({top:0,behavior:'smooth'}); });

  apply();
})();
</script>
</body>
</html>"""


if __name__ == "__main__":
    build()
