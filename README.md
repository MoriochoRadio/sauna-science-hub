# 🔥 사우나 사이언스 허브 (Sauna Science Hub)

사우나가 건강에 미치는 영향을 다룬 **과학적 연구·임상시험 증거**를 한눈에 보는 사우나 매니아 전용 아카이브.
[PubMed](https://pubmed.ncbi.nlm.nih.gov/) 에서 매일 자동 수집되며, **한국어 번역 + 원문**을 함께 제공하고
GitHub Pages로 무료 호스팅됩니다.

🔗 **라이브 사이트**: https://moriochoradio.github.io/sauna-science-hub/

## ✨ 주요 특징
- **근거 기반**: PubMed(peer-reviewed) 논문만 수집. RCT·임상시험·메타분석 등 **근거 등급(1~5급)** 표시, 1급은 '★ 최고 근거' 배지
- **한국어 번역**: 제목·초록을 키없는 기계번역으로 한국어 제공 (상단 `🌐 원문(EN)` 버튼으로 원문/한글 토글)
- **한눈에 보기**: 심혈관·사망률·인지·대사·호흡기·회복·정신건강·통증·염증 9개 주제 자동 분류
- **키없는 자동화**: API 키 불필요(E-utilities + gtx 번역 모두 무료). 매일 UTC 01:17(한국 10:17) 자동 갱신 + push 시 재배포
- **UX/UI**: 실시간 검색+하이라이트, 주제 필터, 근거등급 필터, 정렬(최신/근거/임상), 결과 카운트, 다크모드, 방법론 패널, 맨위로
- **빌드 타임 렌더**: 브라우저 파싱 없이 완성된 정적 HTML 출력 (빈 페이지 버그 차단)

## 🗂️ 구성
| 경로 | 설명 |
|------|------|
| `scripts/collect.py` | PubMed 수집 + 한국어 번역 → `data/research.json` |
| `scripts/build.py` | JSON → `index.html` 정적 사이트 생성 (템플릿 방식) |
| `data/research.json` | 수집·번역된 연구 데이터 (자동 갱신) |
| `.github/workflows/daily.yml` | 매일 수집→빌드→커밋→Pages 배포 |

## 🤖 자동화
GitHub Actions가 매일 실행됩니다. 즉시 갱신하려면 **Actions → Sauna Science Hub → Run workflow** 를 누르세요.

## 💻 로컬 실행
```bash
python scripts/collect.py   # PubMed 수집 + 한국어 번역
python scripts/build.py     # index.html 생성
python -m http.server 8000  # http://localhost:8000 에서 확인
```
> 번역 단계는 논문당 약 0.1초 소요 — 90편 기준 수집+번역 약 1~2분.

## 🛠️ 커스터마이징
- **검색 범위**: `scripts/collect.py` 의 `QUERY`
- **주제 분류 키워드**: `scripts/collect.py` 의 `CATEGORIES`
- **근거 등급 매핑**: `scripts/collect.py` 의 `EVIDENCE_LABELS` / `build.py` 의 `EVIDENCE_RANK`
- **배포 시각**: `.github/workflows/daily.yml` 의 cron 표현식 (UTC)

## ⚠️ 면책
교육·정보 목적이며 의학적 조언을 대체하지 않습니다. 기계번역은 참고용이며 정확한 내용은 원문(PubMed)을 확인하세요.
건강 상태에 따른 사우나 이용은 전문의와 상담하세요.
