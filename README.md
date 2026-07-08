# 사우나 사이언스 허브 (Sauna Science Hub)

사우나가 건강에 미치는 영향을 다룬 **과학적 연구·임상시험 증거**를 한눈에 보는 사우나 매니아 전용 아카이브.
[PubMed](https://pubmed.ncbi.nlm.nih.gov/) 에서 매일 자동 수집되며, GitHub Pages로 무료 호스팅됩니다.

## 주요 특징
- **근거 기반**: PubMed(peer-reviewed) 논문만 수집. 무작위 대조 시험(RCT)·임상시험·메타분석 등 증거 수준 표시
- **한눈에 보기**: 심혈관·사망률·인지·대사·회복·정신건강 등 주제별 분류
- **키없는 자동화**: API 키 불필요(E-utilities 무료). 매일 UTC 01:17(한국 10:17) 자동 갱신 + push 시 재배포
- **한국어 UX**: 실시간 검색, 주제 필터, 다크모드, 증거 등급 배지
- **빌드 타임 렌더**: 브라우저 파싱 없이 완성된 정적 HTML 출력 (빈 페이지 버그 차단)

## 구성
| 경로 | 설명 |
|------|------|
| `scripts/collect.py` | PubMed E-utilities 수집 → `data/research.json` |
| `scripts/build.py` | JSON → `index.html` 정적 사이트 생성 |
| `data/research.json` | 수집된 연구 데이터 (자동 갱신) |
| `.github/workflows/daily.yml` | 매일 수집→빌드→커밋→Pages 배포 |

## 자동화
GitHub Actions가 매일 실행됩니다. 즉시 갱신하고 싶으면 **Actions → Sauna Science Hub → Run workflow** 를 누르세요.

## 로컬 실행
```bash
python scripts/collect.py   # PubMed에서 수집
python scripts/build.py     # index.html 생성
python -m http.server 8000  # http://localhost:8000 에서 확인
```

## 커스터마이징
- **검색 범위**: `scripts/collect.py` 의 `QUERY` 수정
- **주제 분류**: `scripts/collect.py` 의 `CATEGORIES` 키워드 추가/수정
- **배포 시각**: `.github/workflows/daily.yml` 의 cron 표현식 (UTC)

## 면책
교육·정보 목적이며 의학적 조언을 대체하지 않습니다. 건강 상태에 따른 사우나 이용은 전문의와 상담하세요.
