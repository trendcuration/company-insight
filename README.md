# Company Insight (기업인사이트)

**기업명 입력 → DART 공시 + 증권 데이터 기반 인포그래픽 리포트 생성 앱**

## 개요
기업명을 입력하면 DART(전자공시시스템) 공시자료와 증권 데이터를 바탕으로 재무제표, 배당성향, 증권가 전망, 현재주가를 종합 분석한 인포그래픽 리포트(PNG)를 생성합니다.

## 주요 기능
- **재무제표 분석**: 최근 3개년 매출·영업이익·순이익·자산·부채·자본
- **배당 정보**: 주당배당금(DPS), 배당성향, 시가배당률
- **증권가 전망**: 목표주가 컨센서스, 투자의견 분포
- **실시간 주가**: 현재가, 시가총액, PER/PBR
- **인포그래픽 PNG**: 1200×1600px 디자인 이미지 자동 생성 및 다운로드

## 기술 스택
- Python 3.11 + FastAPI
- Pillow (인포그래픽 렌더링)
- DART Open API (재무제표·배당정보)
- 네이버 금융 (주가·증권사 컨센서스)

## 설치 및 실행

### 1. 환경변수 설정
```bash
cp .env.example .env
# DART_API_KEY= 발급받은 API 키 입력
```

> DART API 키 발급: https://opendart.fss.or.kr → 회원가입 → API 키 발급 (무료)

### 2. 실행
```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### 3. 브라우저 접속
```
http://localhost:8080
```

## API
```
POST /api/report/{company_name}
→ 인포그래픽 PNG 이미지 반환
```

## 프로젝트 구조
```
company-insight/
├── app/
│   ├── main.py              # FastAPI 앱 진입점
│   ├── routes/report.py     # 리포트 API 엔드포인트
│   ├── services/
│   │   ├── dart_service.py    # DART API 통신
│   │   ├── stock_service.py   # 주가/증권사 스크래핑
│   │   └── infographic.py     # Pillow 이미지 생성
│   ├── models/report.py      # 데이터 모델
│   ├── static/               # CSS/JS
│   └── templates/            # HTML
├── data/                     # 캐시 파일
├── .env.example
├── requirements.txt
└── README.md
```
