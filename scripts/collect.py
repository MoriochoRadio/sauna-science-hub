#!/usr/bin/env python3
"""
Sauna Science Hub — 키없는(keyless) PubMed 수집기.

사우나의 과학적 근거(심혈관, 사망률, 인지, 대사, 회복, 정신건강 등)를
PubMed E-utilities 에서 가져와 data/research.json 으로 저장한다.
무료 · API 키 불필요 · 매일 GitHub Actions 에서 실행.
"""
import json
import sys
import time
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
OUT = "data/research.json"
CACHE = "data/translations.json"

# 사우나 과학 증거를 좁히는 쿼리 (PubMed 검색 구문)
QUERY = '(sauna OR "sauna bathing" OR "thermal bathing") AND (health OR cardiovascular OR mortality OR "clinical trial" OR "randomized" OR cognition OR metabolic OR recovery OR "blood pressure")'
RETMAX = 90

# 카테고리 매핑 (키워드 -> 한국어 라벨)
CATEGORIES = {
    "심혈관": ["cardiovascular", "heart", "cardiac", "coronary", "myocardial", "arterial", "blood pressure", "hypertension", "vascular"],
    "사망률·수명": ["mortality", "mortalit", "longevity", "life expectancy", "all-cause", "survival", "death"],
    "인지·뇌": ["cognit", "brain", "neuro", "alzheimer", "dementia", "memory", "mental"],
    "대사·체중": ["metabolic", "glucose", "insulin", "diabet", "weight", "obesity", "lipid", "cholesterol"],
    "호흡기": ["respiratory", "lung", "asthma", "pneumonia", "copd"],
    "회복·운동": ["recovery", "athletic", "exercise", "performance", "muscle", "endurance"],
    "정신건강": ["depression", "stress", "mood", "anxiety", "well-being", "wellbeing", "psycholog"],
    "통증·염증": ["pain", "inflammation", "arthritis", "rheumatoid", "fibromyalgia"],
}

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

def translate_cached(cache, text, sl="en", tl="ko", key=None):
    """캐시 우선 번역. key 는 캐시 구분용(PMID+필드)."""
    if not text or not text.strip():
        return ""
    if key:
        ck = f"{sl}>{tl}:{key}"
        if ck in cache and cache[ck]:
            return cache[ck]
    tr = translate(text, sl, tl)
    if key and tr:
        cache[ck] = tr
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


def fetch_details(pmids):
    out = []
    for i in range(0, len(pmids), 100):
        batch = pmids[i:i + 100]
        url = f"{BASE}/efetch.fcgi?db=pubmed&id={','.join(batch)}&retmode=xml"
        xml = fetch_xml(url)
        root = ET.fromstring(xml)
        for art in root.iter("PubmedArticle"):
            out.append(parse_article(art))
        time.sleep(0.4)
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


def parse_article(art):
    cite = art.find(".//Article")
    if cite is None:
        return None
    pmid = _text(art, ".//PMID")
    title = _text(cite, "./ArticleTitle")
    abstract = _text(cite, "./Abstract/AbstractText")
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
    doi = ""
    for aid in art.findall(".//ArticleIdList/ArticleId"):
        if aid.get("IdType") == "doi":
            doi = aid.text.strip()
    pubtypes = [_text(pt, ".") for pt in art.findall(".//PublicationTypeList/PublicationType")]
    evidence = "기타"
    for pt in pubtypes:
        if pt in EVIDENCE_LABELS:
            evidence = EVIDENCE_LABELS[pt]
            break
    is_clinical = any("Trial" in pt or "Clinical" in pt or "Randomized" in pt for pt in pubtypes)
    blob = (title + " " + abstract).lower()
    cats = []
    for label, kws in CATEGORIES.items():
        if any(k in blob for k in kws):
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
    migrated = 0
    try:
        old = json.load(open(OUT, encoding="utf-8"))
        for a in old.get("articles", []):
            pid = a.get("pmid", "")
            if pid and a.get("title_ko"):
                k = f"en>ko:{pid}:title"
                if k not in cache:
                    cache[k] = a["title_ko"]; migrated += 1
            if pid and a.get("abstract_ko"):
                k = f"en>ko:{pid}:abstract"
                if k not in cache:
                    cache[k] = a["abstract_ko"]; migrated += 1
        if migrated:
            save_cache(cache)
            print(f"[collect] 기존 번역 {migrated}건 캐시 적재", file=sys.stderr)
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
