#!/usr/bin/env python3
"""
Sauna Science Hub — 키없는(keyless) PubMed 수집기.

사우나의 과학적 근거(심혈관, 사망률, 인지, 대사, 회복, 정신건강 등)를
PubMed E-utilities 에서 가져와 data/research.json 으로 저장한다.
무료 · API 키 불필요 · 매일 GitHub Actions 에서 실행.
"""
import hashlib
import json
import sys
import time
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
OUT = "data/research.json"
CACHE = "data/translations.json"

# 사우나 과학 증거를 좁히는 쿼리 (PubMed 검색 구문)
# 사우나 쪽은 [tiab](제목·초록·저자 키워드)로 묶는다. 필드 태그 없이 쓰면 PubMed 자동 확장으로
# "thermal bathing" 이 (thermal AND bathing), sauna 가 (steam AND bath)까지 넓어져
# 신생아 목욕·해변 열 지각 같은 무관 논문이 절반 넘게 섞였다.
# 온천요법(balneotherapy)·해수요법은 사이트 범위(사우나) 밖이라 넣지 않는다.
QUERY = '(sauna[tiab] OR saunas[tiab] OR "sauna bathing"[tiab] OR "Waon therapy"[tiab] OR "Steam Bath"[mh]) AND (health OR cardiovascular OR mortality OR "clinical trial" OR "randomized" OR cognition OR metabolic OR recovery OR "blood pressure")'
RETMAX = 90

# 수집 후 한 번 더 거르는 사우나 어휘 — 제목·초록·저자 키워드 중 한 곳에는 있어야 채택
SAUNA_TERMS = re.compile(r"\bsaunas?\b|\bwaon\b|\bsteam[- ]?(?:baths?|rooms?)\b", re.I)

# 카테고리 매핑 (정규식 -> 한국어 라벨, 소문자 제목+초록에 적용)
# \b 로 단어 앞머리를 고정해 부분 문자열 오탐(experimental/environmental → mental,
# Spain → pain)을 막는다. vascular·metabolic·weight 는 합성어(cerebrovascular,
# cardiometabolic, overweight)를 살리려고 앞 경계를 두지 않는다.
# 운동생리 연구에 흔한 측정어는 뺀다: 단독 heart rate(심박, HRV 는 유지), heat/oxidative 등 생리적 stress,
# neuromuscular, brain natriuretic peptide(심부전 표지자).
_PHYS_STRESS = ("heat", "thermal", "oxidative", "cold", "shear", "hemodynamic", "haemodynamic",
                "physiological", "cardiovascular", "metabolic", "nitrosative", "mechanical", "environmental")
CATEGORIES = {
    "심혈관": [r"\bcardiovascular", r"\bheart\b(?![\s-]+rates?\b(?![\s-]+variability))",r"\bcardiac", r"\bcoronary", r"\bmyocardial",
               r"\barterial", r"\bblood pressure", r"\bhypertension", r"vascular"],
    "사망률·수명": [r"\bmortalit", r"\blongevity", r"\blife expectancy", r"\ball-cause", r"\bsurvival", r"\bdeath"],
    "인지·뇌": [r"\bcognit", r"\bbrain\b(?![\s-]+natriuretic)", r"\bneuro(?!muscular)", r"\balzheimer",
                r"\bdementia", r"\bmemory", r"\bmental\b"],
    "대사·체중": [r"metabolic", r"\bglucose", r"\binsulin", r"\bdiabet", r"weight\b", r"\bobesity", r"\blipid",
                 r"\bcholesterol"],
    "호흡기": [r"\brespiratory", r"\blung", r"\basthma", r"\bpneumonia", r"\bcopd"],
    "회복·운동": [r"\brecovery", r"\bathletic", r"\bexercise", r"\bperformance", r"\bmuscle", r"\bendurance"],
    "정신건강": [r"\bdepression", "".join(rf"(?<!\b{w}[\s-])" for w in _PHYS_STRESS) + r"\bstress", r"\bmood",
                r"\banxiety", r"\bwell-being", r"\bwellbeing", r"\bpsycholog"],
    "통증·염증": [r"\bpain", r"\binflammation", r"\barthritis", r"\brheumatoid", r"\bfibromyalgia"],
}
CATEGORY_RE = {label: re.compile("|".join(pats)) for label, pats in CATEGORIES.items()}

EVIDENCE_LABELS = {
    "Randomized Controlled Trial": "무작위 대조 시험(RCT)",
    "Clinical Trial": "임상시험",
    "Clinical Trial, Phase I": "임상시험 I상",
    "Clinical Trial, Phase II": "임상시험 II상",
    "Clinical Trial, Phase III": "임상시험 III상",
    "Clinical Trial, Phase IV": "임상시험 IV상",
    "Controlled Clinical Trial": "대조 임상시험",
    "Meta-Analysis": "메타분석",
    "Systematic Review": "체계적 문헌고찰",
    "Review": "리뷰",
    "Cohort Study": "코호트 연구",
    "Case-Control Study": "환자-대조 연구",
    "Observational Study": "관찰 연구",
    "Cross-Sectional Study": "단면 연구",
}


def load_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(cache):
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    os.replace(tmp, CACHE)


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "sauna-science-hub/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def src_fp(text):
    """번역 원문 지문(공백 정규화 후 해시). 원문이 바뀌면 캐시를 다시 번역하게 한다."""
    return hashlib.sha1(" ".join(text.split()).encode("utf-8")).hexdigest()[:12]


def translate_cached(cache, text, sl="en", tl="ko", key=None):
    """캐시 우선 번역. key 는 캐시 구분용(PMID+필드). 원문 지문이 같을 때만 캐시를 쓴다."""
    if not text or not text.strip():
        return ""
    if key:
        ck = f"{sl}>{tl}:{key}"
        fp = src_fp(text)
        if cache.get(ck) and cache.get(ck + "#src") == fp:
            return cache[ck]
    tr = translate(text, sl, tl)
    if key and tr:
        cache[ck] = tr
        cache[ck + "#src"] = fp
    return tr


def fetch_xml(url):
    req = urllib.request.Request(url, headers={"User-Agent": "sauna-science-hub/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def translate(text, sl="en", tl="ko"):
    """키없는 Google 번역(gtx). 실패 시 빈 문자열 반환(fallback)."""
    if not text or not text.strip():
        return ""
    try:
        q = urllib.parse.quote(text[:5000])
        url = (f"https://translate.googleapis.com/translate_a/single"
               f"?client=gtx&sl={sl}&tl={tl}&dt=t&q={q}")
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        parts = [seg[0] for seg in data[0] if seg and seg[0]]
        return "".join(parts)
    except Exception as e:
        print(f"[translate] 실패({sl}->{tl}): {str(e)[:80]}", file=sys.stderr)
        return ""
    finally:
        time.sleep(0.12)


def search_pmids():
    q = urllib.parse.quote(QUERY)
    url = f"{BASE}/esearch.fcgi?db=pubmed&term={q}&retmode=json&retmax={RETMAX}&sort=date"
    data = fetch_json(url)
    return data.get("esearchresult", {}).get("idlist", [])


def is_sauna_related(art, a):
    """제목·초록·저자 키워드에 사우나 어휘가 있는지 (검색어 확장으로 딸려 온 무관 논문 제거)."""
    keywords = " ".join(_alltext(k) for k in art.findall(".//KeywordList/Keyword"))
    return bool(SAUNA_TERMS.search(" ".join((a["title"], a["abstract"], keywords))))


def fetch_details(pmids):
    out = []
    dropped = []
    for i in range(0, len(pmids), 100):
        batch = pmids[i:i + 100]
        url = f"{BASE}/efetch.fcgi?db=pubmed&id={','.join(batch)}&retmode=xml"
        xml = fetch_xml(url)
        root = ET.fromstring(xml)
        for art in root.iter("PubmedArticle"):
            a = parse_article(art)
            if not a:
                continue
            if not is_sauna_related(art, a):
                dropped.append(a["pmid"])
                continue
            out.append(a)
        time.sleep(0.4)
    if dropped:
        print(f"[collect] 사우나 어휘 없는 {len(dropped)}편 제외: {', '.join(dropped)}", file=sys.stderr)
    # 한국어 번역 (제목 + 초록). 캐시 우선 — 재번역·rate-limit 방지.
    cache = load_cache()
    cache_hit = 0
    print(f"[collect] 한국어 번역 시작 ({len(out)}편)...", file=sys.stderr)
    done = 0
    for a in out:
        pid = a.get("pmid", "")
        if a.get("title"):
            ko = translate_cached(cache, a["title"], key=f"{pid}:title")
            a["title_ko"] = ko
            if ko and ko == cache.get(f"en>ko:{pid}:title"):
                cache_hit += 1
        if a.get("abstract"):
            a["abstract_ko"] = translate_cached(cache, a["abstract"], key=f"{pid}:abstract")
        done += 1
        if done % 20 == 0:
            print(f"[collect] 번역 {done}/{len(out)} (캐시 히트 누적 {cache_hit})", file=sys.stderr)
    save_cache(cache)
    print(f"[collect] 번역 완료 — 캐시 히트 {cache_hit}건", file=sys.stderr)
    return out


def _text(el, path):
    node = el.find(path)
    return node.text.strip() if node is not None and node.text else ""


def _alltext(node):
    """인라인 태그(<i>, <sup> 등) 뒤의 텍스트까지 포함한 전체 텍스트(공백 정규화)."""
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def _abstract(cite):
    """구조화 초록(BACKGROUND/METHODS/RESULTS…)의 모든 단락을 라벨과 함께 이어 붙인다."""
    parts = []
    for node in cite.findall("./Abstract/AbstractText"):
        body = _alltext(node)
        if not body:
            continue
        label = (node.get("Label") or "").strip()
        parts.append(f"{label}: {body}" if label and label.upper() != "UNLABELLED" else body)
    return " ".join(parts)


def parse_article(art):
    cite = art.find(".//Article")
    if cite is None:
        return None
    pmid = _text(art, ".//PMID")
    title = _alltext(cite.find("./ArticleTitle"))
    abstract = _abstract(cite)
    journal = _text(cite, "./Journal/Title")
    year = ""
    for tag in (".//Journal/JournalIssue/PubDate/Year",
                ".//Article/ArticleDate/Year"):
        year = _text(art, tag)
        if year:
            break
    if not year:
        medline = _text(art, ".//Journal/JournalIssue/PubDate/MedlineDate")
        if medline:
            year = medline[:4]
    volume = _text(cite, "./Journal/JournalIssue/Volume")
    issue = _text(cite, "./Journal/JournalIssue/Issue")
    pages = _text(cite, "./Pagination/MedlinePgn")
    authors = []
    for au in art.findall(".//AuthorList/Author"):
        last = _text(au, "./LastName")
        fore = _text(au, "./ForeName")
        if last:
            authors.append(f"{last} {fore}".strip())
    authors = authors[:6]
    # 이 논문의 DOI 만: .//ArticleIdList 는 참고문헌(ReferenceList)의 ID 까지 잡으므로
    # PubmedData 바로 아래 목록의 첫 값을 쓰고, 없으면 본문 ELocationID 로 보완한다.
    doi = (_text(art, "./PubmedData/ArticleIdList/ArticleId[@IdType='doi']")
           or _text(cite, "./ELocationID[@EIdType='doi']"))
    pubtypes = [_text(pt, ".") for pt in art.findall(".//PublicationTypeList/PublicationType")]
    evidence = "기타"
    for pt in pubtypes:
        if pt in EVIDENCE_LABELS:
            evidence = EVIDENCE_LABELS[pt]
            break
    is_clinical = any("Trial" in pt or "Clinical" in pt or "Randomized" in pt for pt in pubtypes)
    blob = (title + " " + abstract).lower()
    cats = []
    for label, pat in CATEGORY_RE.items():
        if pat.search(blob):
            cats.append(label)
    if not cats:
        cats = ["기타"]
    return {
        "pmid": pmid,
        "title": title,
        "title_ko": "",
        "abstract": abstract,
        "abstract_ko": "",
        "journal": journal,
        "year": year,
        "volume": volume,
        "issue": issue,
        "pages": pages,
        "authors": authors,
        "doi": doi,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "evidence": evidence,
        "is_clinical": is_clinical,
        "categories": cats,
    }


def main():
    # 기존 research.json 에 이미 번역된 값이 있으면 캐시로 적재 (재번역 방지)
    cache = load_cache()
    migrated = stamped = 0
    try:
        old = json.load(open(OUT, encoding="utf-8"))
        for a in old.get("articles", []):
            pid = a.get("pmid", "")
            for field in ("title", "abstract"):
                ko = a.get(field + "_ko")
                if not (pid and ko):
                    continue
                k = f"en>ko:{pid}:{field}"
                if k not in cache:
                    cache[k] = ko; migrated += 1
                # 지문 없는 옛 캐시: 번역 당시 원문(research.json 에 남은 값)으로 지문을 찍는다.
                # 이후 원문이 달라진 논문(예: 잘렸던 초록)만 다시 번역된다.
                if cache.get(k) == ko and k + "#src" not in cache and a.get(field):
                    cache[k + "#src"] = src_fp(a[field]); stamped += 1
        if migrated or stamped:
            save_cache(cache)
            print(f"[collect] 기존 번역 {migrated}건 캐시 적재, 원문 지문 {stamped}건 기록", file=sys.stderr)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    print(f"[collect] PubMed 검색: {QUERY}", file=sys.stderr)
    pmids = search_pmids()
    print(f"[collect] {len(pmids)}편 검색됨", file=sys.stderr)
    if not pmids:
        print("[collect] 결과 없음 -- 빈 파일 작성", file=sys.stderr)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump({"updated": str(date.today()), "count": 0, "articles": []}, f, ensure_ascii=False, indent=2)
        return
    articles = [a for a in fetch_details(pmids) if a]
    articles.sort(key=lambda a: (a["is_clinical"], a["year"]), reverse=True)
    payload = {
        "updated": str(date.today()),
        "query": QUERY,
        "count": len(articles),
        "clinical_count": sum(1 for a in articles if a["is_clinical"]),
        "articles": articles,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[collect] data/research.json 저장 완료 ({len(articles)}편, 임상 {payload['clinical_count']}편)", file=sys.stderr)


if __name__ == "__main__":
    main()
