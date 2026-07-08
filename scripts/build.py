#!/usr/bin/env python3
"""
Sauna Science Hub — 빌드 타임 정적 사이트 생성기.

data/research.json 을 읽어 index.html 을 생성한다.
브라우저 측 파싱 없이 완성된 HTML을 출력 (Pages에서 즉시 렌더).
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


def esc(s):
    return html.escape(str(s or ""), quote=True)


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
        if len(authors) > 3:
            author_str = ", ".join(authors[:3]) + f" 외 {len(authors)-3}명"
        else:
            author_str = ", ".join(authors)
    else:
        author_str = "저자 미상"
    meta_bits = []
    if a.get("journal"):
        meta_bits.append(esc(a["journal"]))
    if a.get("year"):
        meta_bits.append(esc(a["year"]))
    meta = " · ".join(meta_bits)
    evidence = a.get("evidence", "기타")
    clinical = "clinical" if a.get("is_clinical") else ""
    abstract = esc(a.get("abstract", ""))
    abstract_html = f'<p class="abs">{abstract}</p>' if abstract else ""
    return f"""
    <article class="card {clinical}" data-idx="{idx}">
      <div class="card-top">
        <span class="evi">{esc(evidence)}</span>
        <span class="evi-rank">근거 {EVIDENCE_RANK.get(evidence, 5)}급</span>
      </div>
      <h3><a href="{esc(a['url'])}" target="_blank" rel="noopener">{esc(a.get('title',''))}</a></h3>
      <div class="cats">{cat_html}</div>
      {abstract_html}
      <div class="meta">{meta} · {esc(author_str)}</div>
      <a class="link" href="{esc(a['url'])}" target="_blank" rel="noopener">PubMed에서 전문 보기 →</a>
    </article>"""


def build():
    data = load()
    articles = data.get("articles", [])
    updated = data.get("updated", str(date.today()))
    total = data.get("count", len(articles))
    clinical = data.get("clinical_count", sum(1 for a in articles if a.get("is_clinical")))

    # 카테고리 카운트
    cat_counts = Counter()
    for a in articles:
        for c in a.get("categories", ["기타"]):
            cat_counts[c] += 1

    # 통계 (연도별)
    years = Counter(a.get("year", "") for a in articles if a.get("year"))
    year_stats = ", ".join(f"{y}년 {n}편" for y, n in sorted(years.items(), reverse=True)[:6])

    # 필터 버튼
    filter_btns = ['<button class="fbtn active" data-cat="all">전체 <span class="cnt">{total}</span></button>']
    for c in CATEGORY_META:
        if cat_counts.get(c):
            color = CATEGORY_META[c][0]
            filter_btns.append(
                f'<button class="fbtn" data-cat="{esc(c)}" style="--c:{color}">{esc(c)} <span class="cnt">{cat_counts[c]}</span></button>'
            )
            filter_html = "".join(filter_btns)

    cards_html = "\n".join(card(a, i) for i, a in enumerate(articles))

    html_doc = f"""<!DOCTYPE html>
<html lang="ko" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>사우나 사이언스 허브 — 증거 기반 사우나 연구 아카이브</title>
<meta name="description" content="사우나의 과학적 근거: 심혈관, 사망률, 인지, 대사, 회복, 정신건강 등 PubMed 기반 peer-reviewed 연구 및 임상시험 한눈에 보기.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@600;700&family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:#faf7f2; --bg2:#f3ede3; --ink:#1f1b16; --muted:#6b6258; --line:#e6ddcf;
  --accent:#b45309; --accent2:#c2410c; --card:#ffffff; --shadow:0 1px 3px rgba(60,40,20,.08),0 8px 24px rgba(60,40,20,.06);
}}
[data-theme="dark"] {{
  --bg:#15120e; --bg2:#1e1a14; --ink:#f1e9dd; --muted:#a99e8d; --line:#332c22;
  --accent:#e0913a; --accent2:#f2743d; --card:#211c15; --shadow:0 1px 3px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.35);
}}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:'Noto Sans KR',system-ui,sans-serif; background:var(--bg); color:var(--ink); line-height:1.65; -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:0 22px; }}
header.hero {{ background:linear-gradient(160deg,var(--bg2),var(--bg)); border-bottom:1px solid var(--line); padding:54px 0 40px; }}
.kicker {{ font-size:.8rem; letter-spacing:.22em; text-transform:uppercase; color:var(--accent); font-weight:700; }}
h1 {{ font-family:'Noto Serif KR',serif; font-size:clamp(2rem,5vw,3.1rem); line-height:1.15; margin:10px 0 14px; font-weight:700; }}
.lede {{ max-width:640px; color:var(--muted); font-size:1.05rem; }}
.stats {{ display:flex; flex-wrap:wrap; gap:14px; margin-top:26px; }}
.stat {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:14px 20px; box-shadow:var(--shadow); }}
.stat b {{ display:block; font-family:'Noto Serif KR',serif; font-size:1.7rem; color:var(--accent2); line-height:1; }}
.stat span {{ font-size:.82rem; color:var(--muted); }}
.toolbar {{ position:sticky; top:0; z-index:20; background:var(--bg); border-bottom:1px solid var(--line); padding:14px 0; backdrop-filter:saturate(1.2) blur(6px); }}
.search {{ width:100%; padding:12px 16px; border:1px solid var(--line); border-radius:12px; background:var(--card); color:var(--ink); font-size:1rem; font-family:inherit; }}
.search:focus {{ outline:2px solid var(--accent); outline-offset:1px; }}
.filters {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; align-items:center; }}
.fbtn {{ font-family:inherit; font-size:.85rem; cursor:pointer; border:1px solid var(--line); background:var(--card); color:var(--ink); padding:6px 13px; border-radius:999px; transition:.15s; }}
.fbtn:hover {{ border-color:var(--accent); }}
.fbtn.active {{ background:var(--accent); border-color:var(--accent); color:#fff; }}
.fbtn .cnt {{ opacity:.7; font-size:.78rem; margin-left:2px; }}
.darktoggle {{ margin-left:auto; cursor:pointer; border:1px solid var(--line); background:var(--card); color:var(--ink); border-radius:999px; padding:6px 14px; font-size:.85rem; font-family:inherit; }}
main {{ padding:30px 0 70px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:18px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:16px; padding:20px; box-shadow:var(--shadow); display:flex; flex-direction:column; gap:10px; transition:.18s; border-left:4px solid var(--accent); }}
.card.clinical {{ border-left-color:var(--accent2); }}
.card:hover {{ transform:translateY(-3px); box-shadow:0 4px 10px rgba(60,40,20,.1),0 16px 36px rgba(60,40,20,.1); }}
.card-top {{ display:flex; gap:8px; align-items:center; }}
.evi {{ font-size:.74rem; font-weight:700; background:var(--bg2); color:var(--accent); padding:3px 9px; border-radius:999px; border:1px solid var(--line); }}
.evi-rank {{ font-size:.72rem; color:var(--muted); }}
.card h3 {{ font-family:'Noto Serif KR',serif; font-size:1.12rem; line-height:1.35; font-weight:600; }}
.card h3 a {{ color:var(--ink); text-decoration:none; }}
.card h3 a:hover {{ color:var(--accent); text-decoration:underline; }}
.cats {{ display:flex; flex-wrap:wrap; gap:6px; }}
.tag {{ font-size:.72rem; color:#fff; background:var(--c,#64748b); padding:2px 9px; border-radius:999px; font-weight:500; }}
.abs {{ font-size:.88rem; color:var(--muted); display:-webkit-box; -webkit-line-clamp:4; -webkit-box-orient:vertical; overflow:hidden; }}
.meta {{ font-size:.8rem; color:var(--muted); margin-top:auto; }}
.link {{ font-size:.82rem; font-weight:600; color:var(--accent2); text-decoration:none; }}
.link:hover {{ text-decoration:underline; }}
footer {{ border-top:1px solid var(--line); background:var(--bg2); padding:30px 0; color:var(--muted); font-size:.85rem; }}
footer a {{ color:var(--accent); }}
.empty {{ text-align:center; padding:80px 20px; color:var(--muted); }}
.nores {{ text-align:center; padding:40px; color:var(--muted); display:none; }}
mark {{ background:#ffe08a; color:#1f1b16; border-radius:3px; padding:0 2px; }}
@media (max-width:560px) {{ .grid {{ grid-template-columns:1fr; }} h1 {{ font-size:2rem; }} }}
</style>
</head>
<body>
<header class="hero">
  <div class="wrap">
    <div class="kicker">Evidence-Based Sauna Research</div>
    <h1>사우나 사이언스 허브</h1>
    <p class="lede">사우나가 몸에 미치는 영향을 다룬 과학적 연구와 임상시험을 한곳에서. PubMed에서 매일 자동 수집되는 근거 기반 자료 아카이브입니다.</p>
    <div class="stats">
      <div class="stat"><b>{total}</b><span>수집 논문</span></div>
      <div class="stat"><b>{clinical}</b><span>임상시험 · RCT</span></div>
      <div class="stat"><b>{len(cat_counts)}</b><span>주제 분류</span></div>
      <div class="stat"><b>{esc(updated)}</b><span>최종 업데이트</span></div>
    </div>
  </div>
</header>

<div class="toolbar">
  <div class="wrap">
    <input id="search" class="search" type="search" placeholder="논문 제목·초록·저널 검색… (예: blood pressure, dementia, recovery)" aria-label="검색">
    <div class="filters">
      {filter_html}
      <button class="darktoggle" id="dark">🌙 다크모드</button>
    </div>
  </div>
</div>

<main>
  <div class="wrap">
    <div class="grid" id="grid">
      {cards_html}
    </div>
    <div class="nores" id="nores">검색 결과가 없습니다.</div>
    <p class="empty" style="display:{ 'block' if total==0 else 'none' }">아직 수집된 자료가 없습니다. 곧 자동 업데이트됩니다.</p>
    <p style="color:var(--muted);font-size:.8rem;margin-top:24px;">연도별 분포: {esc(year_stats) or '—'}</p>
  </div>
</main>

<footer>
  <div class="wrap">
    <p>사우나 사이언스 허브 · <a href="https://pubmed.ncbi.nlm.nih.gov/" target="_blank" rel="noopener">PubMed</a> E-utilities 기반 무료 키없는 자동 수집. 모든 자료는 원 논문 출처(PubMed)로 연결됩니다.</p>
    <p style="margin-top:6px;">본 사이트는 교육·정보 목적이며 의학적 조언을 대체하지 않습니다. 건강 상태에 따른 사우나 이용은 전문의와 상담하세요.</p>
  </div>
</footer>

<script>
(function() {{
  var grid = document.getElementById('grid');
  var cards = Array.prototype.slice.call(grid.querySelectorAll('.card'));
  var search = document.getElementById('search');
  var nores = document.getElementById('nores');
  var activeCat = 'all';

  function norm(s) {{ return (s||'').toLowerCase(); }}

  function apply() {{
    var q = norm(search.value).trim();
    var shown = 0;
    cards.forEach(function(c) {{
      var txt = norm(c.textContent);
      var catOk = activeCat === 'all' || c.querySelector('.tag') && Array.prototype.some.call(c.querySelectorAll('.tag'), function(t){{ return t.textContent.trim() === activeCat; }});
      var match = !q || txt.indexOf(q) !== -1;
      var visible = catOk && match;
      c.style.display = visible ? '' : 'none';
      if (visible) {{
        shown++;
        if (q) highlight(c, q); else clearHL(c);
      }} else clearHL(c);
    }});
    nores.style.display = shown === 0 ? 'block' : 'none';
  }}

  function highlight(card, q) {{
    clearHL(card);
    card.querySelectorAll('h3 a, .abs').forEach(function(node) {{
      var re = new RegExp('('+q.replace(/[.*+?^${{}}()|[\]\\\\]/g,'\\\\$&')+')','gi');
      node.innerHTML = node.innerHTML.replace(re, '<mark>$1</mark>');
    }});
  }}
  function clearHL(card) {{
    card.querySelectorAll('mark').forEach(function(m) {{
      var p = m.parentNode; if(!p) return; p.replaceChild(document.createTextNode(m.textContent), m); p.normalize();
    }});
  }}

  search.addEventListener('input', apply);

  document.querySelectorAll('.fbtn').forEach(function(b) {{
    b.addEventListener('click', function() {{
      document.querySelectorAll('.fbtn').forEach(function(x){{ x.classList.remove('active'); }});
      b.classList.add('active');
      activeCat = b.getAttribute('data-cat');
      apply();
    }});
  }});

  // 다크모드
  var btn = document.getElementById('dark');
  var saved = localStorage.getItem('ssh-theme');
  if (saved === 'dark') setDark(true);
  btn.addEventListener('click', function() {{
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    setDark(!isDark);
  }});
  function setDark(on) {{
    document.documentElement.setAttribute('data-theme', on ? 'dark' : 'light');
    btn.textContent = on ? '☀️ 라이트모드' : '🌙 다크모드';
    localStorage.setItem('ssh-theme', on ? 'dark' : 'light');
  }}
}})();
</script>
</body>
</html>"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print(f"[build] index.html 생성 완료 ({len(articles)}편)", file=sys.stderr)


if __name__ == "__main__":
    build()
