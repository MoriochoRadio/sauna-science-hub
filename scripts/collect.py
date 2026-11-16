#!/usr/bin/env python3
"""
Sauna Science Hub — 키없는(keyless) PubMed 수집기.

사우나의 과학적 근거(심혈관, 사망률, 인지, 대사, 회복, 정신건강 등)를
PubMed E-utilities 에서 가져와 data/research.json 으로 저장한다.
무료 · API 키 불필요 · 매일 GitHub Actions 에서 실행.
"""
import hashlib
import http.client
import json
import sys
import time
import os
import re
import urllib.error
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
_BASE_QUERY = ('(sauna[tiab] OR saunas[tiab] OR "sauna bathing"[tiab] OR "Waon therapy"[tiab] OR "Steam Bath"[mh]) '
               'AND (health OR cardiovascular OR mortality OR "clinical trial" OR "randomized" OR cognition '
               'OR metabolic OR recovery OR "blood pressure")')
# 초록에 sauna 가 '장소·수단'으로만 나오는 무관 주제 — 게이 사우나(MSM 성행동·성병 연구), 격투기
# 감량(사우나는 탈수 수단 중 하나), HFpEF 생쥐 'SAUNA 모델' 약어. 제목에 sauna 가 있으면 살린다.
# ("SAUNA trial" 은 PubMed 구문 색인에 없어 무시되므로 수집 후 필터(SAUNA_ACRONYM)에서 거른다.)
_OFF_TOPIC_QUERY = ('("men who have sex with men"[tiab] OR "sexual minority men"[tiab] OR gay[tiab] OR bisexual[tiab] '
                    'OR "sex-on-premises"[tiab] OR chemsex[tiab] OR "sexually transmitted"[tiab] '
                    'OR "weight cutting"[tiab] OR "weight cut"[tiab] OR "rapid weight loss"[tiab] '
                    'OR "rapid weight reduction"[tiab] OR "SAUNA model"[tiab] OR "SAUNA-induced"[tiab])')
QUERY = f"({_BASE_QUERY}) NOT ({_OFF_TOPIC_QUERY} NOT (sauna[ti] OR saunas[ti]))"
RETMAX = 90        # 사이트에 싣는 편수
SEARCH_MAX = 150   # 검색 창 — 수집 후 필터로 빠지는 몫을 채우려고 RETMAX 보다 넉넉히 받는다

# 수집 후 한 번 더 거르는 사우나 어휘 — 제목·초록·저자 키워드 중 한 곳에는 있어야 채택
SAUNA_TERMS = re.compile(r"\bsaunas?\b|\bwaon\b|\bsteam[- ]?(?:baths?|rooms?)\b", re.I)
# 대문자 SAUNA 는 대개 사우나가 아닌 약어다 — HFpEF 생쥐 모델(Salty drinking water/Unilateral
# Nephrectomy/Aldosterone), 신경내분비종양 'SAUNA trial'. 단 SAUNA-HFpEF 는 실제 사우나 시험이라 예외.
SAUNA_ACRONYM = re.compile(r"\bSAUNA\b(?!-HFpEF)")
# 초록에 sauna 가 한 번뿐이면, 온열·냉각 요법 맥락이 함께 있어야 사우나 연구로 본다.
# (환경 열·직업성 열은 넣지 않는다 — 'heat exposure'·'heat stress' 는 일부러 뺐다)
HEAT_THERAPY = re.compile(
    r"heat therap|thermal therap|thermotherap|passive(?:ly)? heat|heat (?:intervention|stimul)|"
    r"thermal intervention|hyperthermia|hot[- ]water (?:immersion|bath)|cold[- ]water immersion|"
    r"contrast therap|cryotherap|cryostimulation|balneotherap|hydrotherap|kaumatherap|infrared|hormesis", re.I)
# 제목에 sauna 가 없을 때 무관 주제로 보는 단서 (_OFF_TOPIC_QUERY 를 빠져나온 변형까지)
OFF_TOPIC = re.compile(
    r"\bmen who have sex with men\b|\bMSM\b|\bgay\b|\bbisexual\b|sex-on-premises|\bchemsex\b|\bslamming\b|"
    r"\bsexual(?:ly)? (?:behaviou?rs?|transmitted|partners?)\b|\bmpox\b|\bHIV\b|"
    r"\bweight[- ]cut|\brapid weight (?:loss|reduction)\b|\bweight[- ]loss (?:practices?|methods?)\b|\bWL methods?\b",
    re.I)

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

# PubMed PublicationType -> 근거 라벨. 위에 있을수록 우선한다(여러 유형이 붙으면 PubMed 나열
# 순서가 아니라 더 높은 근거를 택함 — 예: Systematic Review + Meta-Analysis → 메타분석).
EVIDENCE_LABELS = {
    "Meta-Analysis": "메타분석",
    "Randomized Controlled Trial": "무작위 대조 시험(RCT)",
    "Systematic Review": "체계적 문헌고찰",
    "Controlled Clinical Trial": "대조 임상시험",
    "Clinical Trial, Phase I": "임상시험 I상",
    "Clinical Trial, Phase II": "임상시험 II상",
    "Clinical Trial, Phase III": "임상시험 III상",
    "Clinical Trial, Phase IV": "임상시험 IV상",
    "Clinical Trial": "임상시험",
    "Cohort Study": "코호트 연구",
    "Case-Control Study": "환자-대조 연구",
    "Observational Study": "관찰 연구",
    "Cross-Sectional Study": "단면 연구",
    "Case Reports": "증례 보고",
    "Review": "리뷰",
    "Scoping Review": "리뷰",
    "Editorial": "사설·논평",
    "Comment": "사설·논평",
    "Letter": "서신",
    "Clinical Trial Protocol": "연구 프로토콜",
}

# PublicationType 이 'Journal Article' 뿐인 논문(대개 MEDLINE 색인 전 최신 논문)은 제목, 없으면
# 초록의 설계 키워드로 유형을 '추정'한다. 휴리스틱이라 라벨에 (추정)을 붙이고 build.py 에서
# 한 단계 낮춰 표시한다. 단서가 없으면 UNTYPED.
UNTYPED = "원저(유형 미표기)"
_DESIGN_HINTS = [
    (r"\bmeta-?analys[ie]s\b", "메타분석(추정)"),
    (r"\bsystematic (?:literature )?review\b", "체계적 문헌고찰(추정)"),
    (r"\b(?:this|narrative|scoping|literature|integrative|critical|umbrella) review\b", "리뷰(추정)"),
    (r"(?<!non-)\brandomi[sz]ed\b|\brandomly (?:assigned|allocated)\b", "무작위 시험(추정)"),
    (r"\b(?:clinical|controlled|pilot|feasibility|single-arm) trial\b", "임상시험(추정)"),
    (r"\bcase-control\b", "환자-대조 연구(추정)"),
    (r"\bcohort\b", "코호트 연구(추정)"),
    (r"\bcross-sectional\b", "단면 연구(추정)"),
]
DESIGN_HINTS = [(re.compile(p, re.I), label) for p, label in _DESIGN_HINTS]
TITLE_REVIEW = re.compile(r"\breview\b", re.I)


def guess_design(title, abstract):
    """제목 → 초록 순으로 설계 키워드를 찾아 (추정) 라벨을 돌려준다(제목의 review 는 단독어도 인정)."""
    for pat, label in DESIGN_HINTS:
        if pat.search(title):
            return label
    if TITLE_REVIEW.search(title):
        return "리뷰(추정)"
    for pat, label in DESIGN_HINTS:
        if pat.search(abstract):
            return label
    return UNTYPED


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


# PubMed 요청 재시도 — 11-05 실행이 esearch 의 일시적 HTTP 500 한 번에 그대로 실패했다.
# 429·5xx·타임아웃·연결 끊김만 지수 백오프(2·4·8초)로 최대 4번까지 시도하고, 4xx 는 바로 올린다.
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_TRIES = 4
BACKOFF = 2.0
RETRY_AFTER_CAP = 60
# NCBI E-utilities 는 API 키 없이 초당 3회까지 — 모든 요청(재시도 포함) 사이를 0.34초 이상 띄운다.
EUTILS_MIN_INTERVAL = 0.34
_last_request = [0.0]


def _throttle():
    wait = _last_request[0] + EUTILS_MIN_INTERVAL - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request[0] = time.monotonic()


def _retry_after(err):
    """429/503 응답의 Retry-After(초)를 존중하되 상한을 둔다. 없거나 날짜 형식이면 None."""
    try:
        return min(float(err.headers.get("Retry-After")), RETRY_AFTER_CAP)
    except (AttributeError, TypeError, ValueError):
        return None


def http_get(url, timeout=30):
    """E-utilities GET (텍스트). 일시적 오류는 백오프 후 재시도, 끝내 실패하면 마지막 예외를 올린다."""
    for attempt in range(1, MAX_TRIES + 1):
        _throttle()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sauna-science-hub/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:   # URLError 의 하위 클래스라 먼저 잡는다
            if e.code not in RETRY_STATUS or attempt == MAX_TRIES:
                raise
            reason, delay = f"HTTP {e.code}", _retry_after(e) or BACKOFF ** attempt
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as e:
            if attempt == MAX_TRIES:
                raise
            reason, delay = type(e).__name__, BACKOFF ** attempt
        print(f"[collect] PubMed 요청 실패({reason}) — {delay:.0f}초 뒤 재시도 ({attempt}/{MAX_TRIES - 1})",
              file=sys.stderr)
        time.sleep(delay)


def fetch_json(url):
    return json.loads(http_get(url))

def src_fp(text):
    """번역 원문 지문(공백 정규화 후 해시). 원문이 바뀌면 캐시를 다시 번역하게 한다."""
    return hashlib.sha1(" ".join(text.split()).encode("utf-8")).hexdigest()[:12]


# 번역 집계 — 캐시 재사용 / 새 번역 / 실패(빈 값). 실패 건은 원문만 표시되고 다음 실행에서 재시도된다.
TR_STATS = {"cached": 0, "translated": 0, "failed": 0}


def translate_cached(cache, text, sl="en", tl="ko", key=None):
    """캐시 우선 번역. key 는 캐시 구분용(PMID+필드). 원문 지문이 같을 때만 캐시를 쓴다."""
    if not text or not text.strip():
        return ""
    if key:
        ck = f"{sl}>{tl}:{key}"
        fp = src_fp(text)
        if cache.get(ck) and cache.get(ck + "#src") == fp:
            TR_STATS["cached"] += 1
            return cache[ck]
    tr = translate(text, sl, tl)
    TR_STATS["translated" if tr else "failed"] += 1
    if key and tr:
        cache[ck] = tr
        cache[ck + "#src"] = fp
    return tr


def fetch_xml(url):
    return http_get(url)


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
    url = f"{BASE}/esearch.fcgi?db=pubmed&term={q}&retmode=json&retmax={SEARCH_MAX}&sort=date"
    data = fetch_json(url)
    res = data.get("esearchresult")
    # 200 응답이어도 본문이 오류일 수 있다 — 빈 결과로 착각하지 말고 실패로 올린다.
    if not isinstance(res, dict) or "ERROR" in res or "idlist" not in res:
        raise RuntimeError(f"esearch 응답 오류: {str(res or data)[:200]}")
    return res["idlist"]


def _sauna_mentions(text):
    """사우나 어휘 등장 횟수. 대문자 약어 SAUNA(생쥐 모델·다른 시험 이름)는 세지 않는다."""
    if not text:
        return 0
    if not text.isupper():   # 제목 전체가 대문자면 약어와 구분할 수 없어 그대로 센다
        text = SAUNA_ACRONYM.sub(" ", text)
    return len(SAUNA_TERMS.findall(text))


def relevance(title, abstract, keywords=(), mesh=()):
    """사우나·온열요법 연구인지 판정해 (채택 여부, 사유)를 돌려준다.

    초록 한 줄에 sauna 가 '장소·수단·배제 기준'으로만 나오는 논문(게이 사우나 성행동 조사, 격투기
    감량 방법 설문, 땀 센서 시험 환경, 사우나에서 넘어진 증례 등)을 거른다.
    1) 제목에 사우나 어휘 → 채택  2) 무관 주제 단서(OFF_TOPIC) → 제외
    3) MeSH 'Steam Bath' 또는 저자 키워드에 사우나 → 채택  4) 초록에 2회 이상 → 채택
    5) 초록에 1회 + 온열·냉각 요법 맥락(HEAT_THERAPY) → 채택  6) 나머지 → 제외
    """
    if _sauna_mentions(title):
        return True, "title"
    m = OFF_TOPIC.search(f"{title} {abstract}")
    if m:
        return False, f"off-topic:{m.group(0)}"
    if "Steam Bath" in mesh or any(_sauna_mentions(k) for k in keywords):
        return True, "keyword"
    n = _sauna_mentions(abstract)
    if n >= 2:
        return True, "abstract"
    if n == 1 and HEAT_THERAPY.search(f"{title} {abstract}"):
        return True, "abstract+heat"
    return False, "incidental" if n else "no-sauna"


def _keywords(art):
    return [_alltext(k) for k in art.findall(".//KeywordList/Keyword")]


def _mesh(art):
    return [_alltext(d) for d in art.findall(".//MeshHeadingList/MeshHeading/DescriptorName")]


def fetch_details(pmids):
    """efetch 로 상세를 받아 파싱·관련성 필터 후 검색 순서(최신순) 그대로 RETMAX 편까지 돌려준다."""
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
            ok, why = relevance(a["title"], a["abstract"], _keywords(art), _mesh(art))
            if not ok:
                dropped.append(f"{a['pmid']}({why})")
                continue
            out.append(a)
    if dropped:
        print(f"[collect] 사우나 연구가 아닌 {len(dropped)}편 제외: {', '.join(dropped)}", file=sys.stderr)
    order = {p: i for i, p in enumerate(pmids)}
    out.sort(key=lambda a: order.get(a["pmid"], len(order)))
    return out[:RETMAX]


def translate_articles(out):
    # 한국어 번역 (제목 + 초록). 캐시 우선 — 재번역·rate-limit 방지.
    cache = load_cache()
    print(f"[collect] 한국어 번역 시작 ({len(out)}편)...", file=sys.stderr)
    done = 0
    for a in out:
        pid = a.get("pmid", "")
        if a.get("title"):
            a["title_ko"] = translate_cached(cache, a["title"], key=f"{pid}:title")
        if a.get("abstract"):
            a["abstract_ko"] = translate_cached(cache, a["abstract"], key=f"{pid}:abstract")
        done += 1
        if done % 20 == 0:
            print(f"[collect] 번역 {done}/{len(out)} (누적 {TR_STATS})", file=sys.stderr)
    save_cache(cache)
    st = TR_STATS
    print(f"[collect] 번역 완료 — 캐시 {st['cached']}건, 신규 {st['translated']}건, 실패 {st['failed']}건", file=sys.stderr)
    if st["failed"]:
        # GitHub Actions 주석(stdout). 비공식 gtx 엔드포인트가 막히면 여기서 먼저 드러난다.
        total = st["translated"] + st["failed"]
        print(f"::warning title=번역 실패::비공식 Google 번역(gtx) {st['failed']}/{total}건 실패 "
              f"— 해당 제목·초록은 원문만 표시되고 다음 실행에서 재시도한다.")
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
    evidence = next((lbl for pt, lbl in EVIDENCE_LABELS.items() if pt in pubtypes), "")
    if not evidence:
        evidence = guess_design(title, abstract)
    # 시험 '계획서'(Clinical Trial Protocol)는 결과가 없으므로 임상 근거로 세지 않는다.
    is_clinical = any(("Trial" in pt or "Clinical" in pt or "Randomized" in pt) and "Protocol" not in pt
                      for pt in pubtypes)
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
    try:
        pmids = search_pmids()
        print(f"[collect] {len(pmids)}편 검색됨", file=sys.stderr)
        articles = [a for a in fetch_details(pmids) if a] if pmids else []
    except Exception as e:   # 재시도까지 실패(5xx 지속·응답 깨짐 등) — 기존 데이터를 지킨다
        return keep_existing(f"PubMed 요청 실패: {type(e).__name__}: {str(e)[:150]}")
    if not articles:
        return keep_existing(f"검색 {len(pmids)}편, 채택 0편")
    translate_articles(articles)
    articles.sort(key=lambda a: (a["is_clinical"], a["year"]), reverse=True)
    payload = {
        "updated": str(date.today()),
        "query": QUERY,
        "count": len(articles),
        "clinical_count": sum(1 for a in articles if a["is_clinical"]),
        "articles": articles,
    }
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT)
    print(f"[collect] data/research.json 저장 완료 ({len(articles)}편, 임상 {payload['clinical_count']}편)", file=sys.stderr)
    return 0


# 수집이 실패하거나 0편이면 research.json 을 덮어쓰지 않는다(빈 사이트 배포 방지). 'updated' 는
# 마지막 성공 수집일로 남으므로, 그날로부터 STALE_DAYS 일 이상 이어질 때만 실행을 실패로 끝내
# GitHub 의 실패 알림 메일로 사람에게 알린다. 그 전의 일시적 장애는 ::warning 주석만 남긴다.
STALE_DAYS = 3


def keep_existing(reason, today=None):
    """기존 데이터를 그대로 두고 종료 코드를 돌려준다 (0 = 계속 배포, 1 = 실패로 알림)."""
    today = today or date.today()
    try:
        with open(OUT, encoding="utf-8") as f:
            old = json.load(f)
        n = len(old.get("articles") or [])
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        old, n = None, 0
    if not n:
        print(f"::error title=PubMed 수집 실패::{reason} — 보존할 기존 데이터도 없다.")
        return 1
    try:
        last = date.fromisoformat(str(old.get("updated", "")))
        stale = (today - last).days
    except ValueError:
        last, stale = "날짜 미상", 0
    if stale >= STALE_DAYS:
        print(f"::error title=PubMed 수집 {stale}일째 실패::{reason} — 마지막 성공 {last}. "
              f"기존 데이터({n}편)는 그대로 두었다. 쿼리·E-utilities 상태를 확인할 것.")
        return 1
    print(f"::warning title=PubMed 수집 실패::{reason} — 기존 데이터({n}편, {last} 수집)를 유지하고 "
          f"다음 실행에서 다시 시도한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
