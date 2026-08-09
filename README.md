# 🧖 사우나 사이언스 허브 (Sauna Science Hub)

**PubMed의 사우나·온열요법 연구를 매일 자동 수집·한국어 번역·근거 등급화해 보여주는 서버리스 정적 아카이브.**
GitHub Actions가 수집→번역→빌드→배포를 전부 수행하며, 운영 비용과 API 키가 전혀 없다.

🔗 **라이브**: https://moriochoradio.github.io/sauna-science-hub/

**기술 스택**: Python 3 표준 라이브러리만(`urllib`·`xml.etree`·`json` — 외부 의존성 0) · PubMed E-utilities · 키 없는 기계번역(캐시) · GitHub Actions · GitHub Pages

## 무엇을 보여주나

- **90여 편의 사우나·온열요법 연구** — 심혈관, 사망률, 인지, 대사, 회복, 정신건강, 통증·염증 등 (PubMed 최신순)
- **근거 수준 표시** — 출판 유형별 RCT·임상시험·메타분석·코호트를 1~5급으로 라벨링. ★는 1급(가장 높은 근거)
- **한국어 번역 + 원문 토글** — 기계번역 한국어와 영문 초록을 함께 제공, 버튼으로 전환
- **정기 간행물 형태의 리스트** — 연도·권호 중심의 에디토리얼 레이아웃, 초록은 기본 접힘(클릭해 펼침)

## 기능

| 기능 | 설명 |
|------|------|
| 검색 | 제목·초록·저널·저자 실시간 검색 (검색어 하이라이트) |
| 주제 필터 | 심혈관·사망률·인지·대사·호흡기·회복·정신건강·통증·염증 |
| 근거 필터 | RCT / 임상시험 / 메타·고찰 / 관찰연구 |
| 정렬 | 최신순 · 근거 수준순 · 임상시험 우선 |
| 보기 설정 | 원문(EN) ↔ 한국어, 라이트/다크모드 (로컬 저장) |

## 동작 구조

```
        ┌──────────── GitHub Actions (매일 KST 10:17 + push 시) ────────────┐
        │                                                                   │
  collect.py ──────────► data/research.json ──► build.py ──► index.html ──► Pages 배포
 (PubMed E-utilities      (논문 메타데이터)      (정적 사이트    (완성된 HTML)
  수집 + 한국어 번역)   + translations.json 캐시    생성기)
```

1. **`collect.py`** — PubMed E-utilities로 사우나 관련 최신 연구를 검색·수집하고, 출판 유형(PublicationType)으로 근거 등급을, 제목·초록 키워드로 주제 카테고리를 분류한다. 제목·초록은 한국어로 기계번역하되 `translations.json` 캐시를 우선 사용한다.
2. **`build.py`** — `research.json`을 읽어 검색·필터·정렬·다크모드가 포함된 완성 정적 `index.html`을 생성한다 (브라우저 측 데이터 파싱 없음).
3. **`daily.yml`** — 위 두 단계를 매일 실행하고, 변경이 있을 때만 데이터를 커밋한 뒤 GitHub Pages로 배포한다. push 시에도 재배포된다.

## 왜 이렇게 만들었나 — 기술 선택 Q&A

**Q. 왜 서버 없는 정적 사이트인가?**
A. 데이터가 하루 1번 바뀌는 아카이브에 서버 렌더링은 낭비다. `build.py`가 빌드 타임에 완성된 HTML을 만들어 브라우저는 파싱 없이 바로 그리고, 호스팅(GitHub Pages)까지 무료라 운영 비용이 0원이다.

**Q. 왜 GitHub Actions인가?**
A. cron 스케줄·수동 실행·push 트리거와 배포(Pages)가 워크플로 파일 하나로 해결되고, 수집 데이터가 커밋으로 남아 이력 추적도 된다. 봇 커밋과 로컬 push가 경합하지 않도록 커밋 전 `git pull --rebase --autostash`를 넣었다.

**Q. 데이터 소스는 왜 PubMed E-utilities인가?**
A. peer-reviewed 연구만 다루는 "증거 기반" 컨셉에 맞는 원천이 PubMed고, E-utilities는 공식 API를 키 없이 무료로 쓸 수 있다. 응답의 출판 유형(RCT·메타분석·코호트 등) 메타데이터 덕분에 근거 등급(1~5급) 자동 라벨링도 가능했다.

**Q. 번역은 왜 키 없는 기계번역 + 캐시인가?**
A. 무료 운영 원칙상 유료 번역 API를 배제했고, 대신 번역값을 `translations.json`에 캐시해 매일 실행돼도 이미 번역된 논문은 재번역하지 않는다 — rate-limit 회피와 실행 시간 단축을 동시에 얻는다. 번역이 실패하면 빈 값으로 두고 원문을 그대로 보여준다(사이트는 깨지지 않음).

**Q. 왜 Python 표준 라이브러리만 쓰나?**
A. HTTP 요청·XML/JSON 파싱·HTML 생성은 `urllib`·`xml.etree`·`json`으로 충분하다. 의존성이 0이면 CI에 설치 단계가 없고, 로컬에서도 Python만 있으면 바로 돌아 매일 도는 파이프라인의 깨질 부품이 줄어든다.

**Q. 근거 수준 라벨링은 왜 넣었나?**
A. 건강 정보는 연구 설계에 따라 신뢰도 차이가 커서, RCT·메타분석(1급)부터 관찰·단면 연구(4급) 이하까지 등급을 구분해 보여줘야 "증거 기반 아카이브"라는 목적에 맞는다. 등급 판정은 PubMed가 제공하는 출판 유형을 그대로 매핑해 자의적 판단을 배제했다.

## 로컬 실행

> Python 3만 있으면 된다. 외부 라이브러리 설치가 필요 없다.

```bash
python3 scripts/collect.py   # PubMed 수집 + 한국어 번역 (인터넷 필요)
python3 scripts/build.py     # index.html 생성
# 생성된 index.html 을 브라우저로 열기
```

- 수집을 건너뛰고 기존 `data/research.json`으로 `build.py`만 실행해도 된다.
- 즉시 갱신하려면: GitHub **Actions 탭 → Sauna Science Hub — Daily Update → Run workflow**

## 파일 구조

```
sauna-science-hub/
├─ .github/workflows/daily.yml   # 매일 자동 수집·빌드·배포
├─ scripts/
│  ├─ collect.py                 # PubMed 수집 + 근거 등급/주제 분류 + 한국어 번역(캐시)
│  └─ build.py                   # 정적 사이트 생성기
├─ data/
│  ├─ research.json              # 수집된 논문 메타데이터
│  └─ translations.json          # 번역 캐시
├─ index.html                    # 빌드 결과 (자동 생성)
└─ README.md
```

## 배운 점

- **캐시로 외부 의존을 길들이기** — 번역값을 파일 캐시에 쌓고, 기존 `research.json`의 번역을 캐시로 마이그레이션해 두면 무료 API의 rate-limit 아래에서도 매일 안정적으로 돌 수 있다. 캐시 저장은 임시 파일 + `os.replace`로 원자적으로 처리해 중간 실패 시 파일 손상을 막았다.
- **실패해도 덜 만들어진 결과를 내놓기** — 번역·수집 일부가 실패해도 예외로 죽는 대신 원문 표시로 대체(fallback)해, 자동화 파이프라인이 "완벽 아니면 중단"이 아니라 매일 무언가를 배포하도록 설계했다.
- **봇이 커밋하는 레포의 push 경합** — 스케줄 봇 커밋과 개발 push가 섞이는 레포에서는 커밋 직전 `git pull --rebase --autostash`가 필수라는 것.

## 면책

교육·정보 목적이며 의학적 조언을 대체하지 않는다. 사우나 이용은 건강 상태에 따라
전문의와 상담하라. 번역 품질은 참고용이며 정확한 내용은 원논문(PubMed) 링크를 확인하라.
