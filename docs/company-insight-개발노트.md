---
type: dev-log
created: 2026. 07. 12.
owner: 가람
project: company-insight
status: 출시 준비 완료 (심사 재제출)
---

# Company Insight (기업정보) 개발 노트

> 기업명 입력 → DART 공시 + 네이버 금융 데이터 기반 기업 분석 리포트 생성 앱
> **토스 앱인토스 미니앱** + 웹 서비스 동시 지원

## 📌 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 레포 | https://github.com/trendcuration/company-insight |
| 백엔드 배포 | Cloudtype (Seoul) — `port-0-company-insight-mrhulzhvffe3669a.sel3.cloudtype.app` |
| 미니앱 | 앱인토스 `.ait` 아티팩트 — 콘솔 등록명 "기업정보" |
| 개발 도구 | Claude Code (원격 세션) |
| 개발 기간 | 2026-06-29 ~ 2026-07-12 |

## 🏗️ 아키텍처

```
[토스 앱 미니앱(.ait)] ──┐
                         ├──> [FastAPI @ Cloudtype] ──> DART Open API (재무·배당)
[웹 브라우저] ───────────┘          │                └──> 네이버 금융 (시세·뉴스·컨센서스)
                                    └──> GET /api/data/{기업명} → JSON
                                    └──> POST /api/report/{기업명} → PNG (레거시)
```

- **프론트**: 미니앱과 웹이 동일한 라이트 테마 + HTML 렌더링 (코드 공유)
- **미니앱**: `@apps-in-toss/web-framework` + Vite, `ait build`로 번들
- **백엔드**: Python 3.11 + FastAPI + httpx(비동기) + BeautifulSoup

## 📂 주요 파일 구조

```
app/
├── main.py                  # FastAPI 진입점, CORS
├── routes/report.py         # /api/data (JSON), /api/report (PNG)
├── services/
│   ├── dart_service.py      # DART: 재무 3개년+중간실적, 배당
│   ├── stock_service.py     # 네이버: 시세·컨센서스·뉴스
│   └── infographic.py       # Pillow PNG (레거시, 나눔고딕 번들)
├── models/report.py         # Pydantic 모델
├── fonts/                   # NanumGothic(Bold).ttf — 서버 한글 렌더링용
├── static/ + templates/     # 웹 프론트 (라이트 테마)
miniapp/
├── granite.config.ts        # 앱인토스 설정 (appName·brand·아이콘)
├── src/main.js              # 리포트 렌더링 + 전면광고
└── company-insight.ait      # 빌드 결과물 (gitignore)
```

## 📊 리포트 구성 (데이터 소스)

| 섹션 | 소스 | 비고 |
|------|------|------|
| 현재 주가·등락률 | `polling.finance.naver.com` JSON | 하락 부호 code 4/5 보정 |
| 시총·PER·PBR·EPS·BPS·52주·거래량·외국인 | `m.stock.naver.com /integration` | 한글 key 라벨 매칭 |
| 실적 (연 3개년 + 당해 상반기/1분기) | DART `fnlttSinglAcnt` | 사업보고서 + 반기(11012)/1분기(11013) 폴백 |
| 재무상태 (자산·부채·자본) | 〃 (BS 계정) | 추가 API 호출 없음 |
| 배당 (DPS·성향·수익률) | DART `alotMatter` | `(연결)` 접두어 정규화 |
| 증권가 전망 (목표주가) | WISEfn → coinfo 폴백 | 라벨 기반 보수적 파싱 |
| 주요 뉴스 5건 | `m.stock.naver.com /api/news` | 제목·언론사·날짜·링크 |

## 🐛 트러블슈팅 기록

> 프로덕션에서 발견·수정한 버그들

1. **한글 전부 □ 깨짐** — Cloudtype 서버에 한글 폰트 없음
   → 나눔고딕(OFL)을 `app/fonts/`에 번들, PNG 라벨의 이모지 제거
2. **재무제표 항상 "없음"** — `fnlttSinglAcnt` 응답에는 `account_id`가 없음 (`AcntAll` 전용 필드)
   → `account_nm`(계정명) + `sj_div` 기반 매칭으로 전환
3. **주가 항상 "없음"** — 서버 IP에서 HTML 스크래핑 불안정
   → 네이버 공개 JSON API 우선, HTML 폴백 체인
4. **한글 파일명 500 에러** — HTTP 헤더는 latin-1만 허용
   → RFC 5987 `filename*=UTF-8''` 인코딩
5. **배당성향 N/A** — `stock_knd` 없는 행이 필터에서 탈락 + `(연결)` 접두어
   → 정규화 매칭
6. **실적이 작년까지만** — `bsns_year` 하드코딩
   → 현재연도-1 우선, -2 폴백 + 당해연도 반기→1분기 중간실적(누적치 사용)
7. **종목 검색 실패** — `searchList.naver` 구조 변경
   → `ac.stock.naver.com` 자동완성 API로 교체
8. **미니앱 심사 반려 — "이름 불일치"** — 콘솔 등록 한국어 앱 이름 "기업정보" ≠
   `granite.config.ts`의 `brand.displayName` "기업인사이트"
   → displayName을 "기업정보"로 통일 후 재제출

## 🎨 디자인 (v2 — 토스 스타일)

- 흰 배경 + 토스 블루 `#3182f6` 포인트, 카드형 레이아웃 (radius 18px)
- **상승 빨강 `#f04452` / 하락 파랑** — 국내 증시 관례 (토스증권과 동일)
- 폰트: 시스템 한글 스택 (Apple SD Gothic Neo / Noto Sans KR)
- 52주 최고·최저 범위 바 (현재가 위치 시각화)
- 헤드카피: "기업명을 입력해서 실시간 기업정보를 조회해보세요"

## 📱 앱인토스 연동

- **전면광고**: 인앱광고 2.0 — `loadFullScreenAd` → `showFullScreenAd`
  - 광고그룹 ID: `ait.v2.live.a557ea481b1d4248`
  - 데이터 수신 완료 후 **2초 대기 → 광고 노출** (조회 중 광고부터 뜨는 문제 방지)
  - 조회 실패 시에는 광고 없이 바로 오류 표시
  - 광고 실패·토스 밖 실행 시 10초 타임아웃으로 우아하게 생략
- **빌드**: `miniapp/`에서 `npx ait build` → `company-insight.ait`
  - 백엔드 주소는 `miniapp/.env`의 `VITE_API_BASE_URL`로 주입 (재빌드 필요)
- 로고: `https://static.toss.im/appsintoss/21275/ea0d96fc-638a-448f-ab14-137cd86f5bcf.png`
- **심사 유의사항**: `brand.displayName`은 콘솔 [기본 정보]의 "한국어 앱 이름"과 반드시 동일해야 함

## 💰 운영 비용

| 항목 | 비용 |
|------|------|
| DART API | 무료 (일 20,000건 한도) |
| 네이버 데이터 | 무료 · **비공식** (차단 리스크 — 성장 시 KIS Developers 등 공식 API 검토) |
| 앱인토스 | 무료 + 광고 수익 발생 |
| Cloudtype | 무료 플랜 (트래픽 증가 시 유료 전환 검토) |
| AI API | 없음 (운영 중 LLM 미사용) |

## ✅ 검증 방식

- 실제 DART/네이버 응답 형식의 **모의(mock) 기반 테스트 25건+** — 파서·엔드포인트·PNG 전체 파이프라인
- 헤드리스 크롬으로 빌드 결과 구동 — 렌더링·JS 오류·광고 지연 타이밍 확인
- ⚠️ 개발 샌드박스에서 외부망(DART·네이버·Cloudtype)이 차단되어 실서버 검증은 배포 후 수동 확인

## 🔜 남은 일 / 아이디어

- [x] 미니앱 표시 이름 콘솔 등록명과 일치 (재제출)
- [ ] 앱인토스 심사 통과 확인
- [ ] 심사 통과 후 실제 광고 노출 여부 재확인 (필요 시 공식 테스트 ID `ait-ad-test-interstitial-id`로 코드/재고 문제 구분)
- [ ] DART 키 재발급 (대화에 노출된 키 교체 권장)
- [ ] 시세 데이터 공식 API 전환 검토 (KIS Developers)
- [ ] 자동완성 검색 UI
- [ ] 리포트 공유하기 (토스 `getTossShareLink`)
- [ ] 관심기업 저장 (`Storage` 브릿지)

## 🔧 운영 명령어 모음

```bash
# 백엔드 로컬 실행
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080

# 미니앱 재빌드 (백엔드 주소 변경 시)
cd miniapp
echo "VITE_API_BASE_URL=https://새주소" > .env
npx ait build          # → company-insight.ait

# 배포 반영: git push origin main → Cloudtype [재배포]
```
