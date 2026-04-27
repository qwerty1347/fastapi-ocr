# FastAPI OCR 서비스

FastAPI 기반 OCR API 서비스입니다. EasyOCR, PaddleOCR, Naver Clova OCR 세 가지 엔진을 선택적으로 호출할 수 있으며, JWT 인증을 통해 보호된 엔드포인트로 제공됩니다. 새로운 OCR 엔진을 쉽게 추가할 수 있도록 엔진 추상화 레이어를 분리했습니다.


## 프로젝트 개요

- FastAPI 기반의 비동기 API 서버
- JWT Bearer 토큰 기반 인증
- EasyOCR / PaddleOCR / Clova OCR 멀티 엔진 지원
- Celery + Redis 기반의 비동기 작업 큐
- SQLAlchemy + aiomysql 기반의 비동기 MySQL 연동 (Alembic 마이그레이션)
- Docker Compose 기반의 로컬 개발 환경
- Pytest 기반의 Unit / Feature 테스트 구성


## 기술 스택

### Runtime
- **Python** 3.11+
- **FastAPI** 0.135.3
- **Uvicorn[standard]** 0.44.0 (auto-reload, uvloop)
- **Pydantic** 2.13.0 / **pydantic-settings** 2.13.1

### OCR Engines
- **EasyOCR** 1.7.2
- **PaddleOCR** 2.9.1 (백엔드: paddlepaddle 2.6.2)
- **Clova OCR** (외부 API)

### Async / Infra
- **Celery** + **Redis** (작업 큐, 모니터링은 Flower)
- **python-jose[cryptography]** (JWT)
- **httpx** (비동기 HTTP 클라이언트)

### Database
- **SQLAlchemy** (ORM)
- **aiomysql** (MySQL 비동기 드라이버)
- **Alembic** (마이그레이션)

### Dev / Test
- **pytest**, **pytest-asyncio**
- **uv** (패키지 매니저 — `uv.lock` 기반 재현 가능한 설치)


## 프로젝트 구조

```text
fastapi-ocr/
├── .docker/                         # Docker 관련 설정 (Dockerfile, entrypoint.sh)
├── app/
│   ├── api/
│   │   ├── __init__.py              # pkgutil 기반 자동 라우터 수집
│   │   └── v1/
│   │       ├── ocr/                 # OCR 엔드포인트 (POST /api/v1/ocr)
│   │       └── token/               # JWT 발급 엔드포인트 (POST /api/v1/token)
│   ├── core/
│   │   ├── celery.py                # Celery 앱 초기화
│   │   ├── config.py                # pydantic-settings 설정 로더
│   │   ├── logging.py               # 로깅 설정
│   │   ├── exceptions/              # 커스텀 예외 및 전역 예외 핸들러
│   │   └── utils/                   # file, http_client, response 유틸
│   ├── dependencies/                # FastAPI 의존성 (auth, file, ocr)
│   ├── module/
│   │   └── ocr/                     # OCR 엔진 구현체
│   │       ├── base.py              # 엔진 추상 기본 클래스 (BaseEngine)
│   │       ├── easyocr.py
│   │       ├── paddleocr.py
│   │       └── clovaocr.py
│   ├── schemas/
│   │   ├── common.py                # SuccessResponse / ErrorResponse 공통 봉투
│   │   ├── enums.py                 # OcrEngine Enum
│   │   ├── ocr/                     # OCR request/response 스키마
│   │   └── token/                   # Token response 스키마
│   ├── services/
│   │   ├── auth/jwt.py              # JWT 발급/검증 서비스
│   │   └── ocr/                     # OCR 비즈니스 로직
│   ├── tasks/                       # Celery 태스크
│   └── main.py                      # FastAPI 애플리케이션 엔트리포인트
├── config/
│   └── settings.py
├── databases/
│   └── mysql/                       # engine.py, session.py
├── storage/
│   ├── screenshots/                 # README용 캡처 이미지
│   └── uploads/                     # 업로드 파일 저장소
├── tests/
│   ├── feature/ocr/
│   └── unit/ocr/
├── docker-compose.yml
├── pyproject.toml                   # 의존성 선언 (uv)
├── pytest.ini
└── uv.lock
```


## API 엔드포인트

| Method | Path | 설명 | 인증 |
|--------|------|------|------|
| POST | `/api/v1/token/` | JWT Access Token 발급 | ❌ |
| POST | `/api/v1/ocr/` | 이미지 업로드 후 OCR 수행 | ✅ Bearer |

**POST `/api/v1/ocr/` 요청 파라미터**
- `file`: 업로드 이미지 (multipart/form-data)
- `engine`: `easyocr` / `paddleocr` / `clovaocr` 중 택1 (Form 필드)

**응답 봉투 포맷**
```json
{
  "code": "200",
  "data": { /* OCR 엔진별 결과 */ }
}
```

에러는 전역 핸들러가 통일된 포맷으로 변환합니다:
```json
{
  "code": "401",
  "message": "Could not validate credentials",
  "errors": []
}
```


## 실행 방법

### 1. 환경변수 설정 (`.env`)

```env
# JWT
JWT_EXPIRE_MINUTES=60
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_SUBJECT=fastapi-ocr

# Clova OCR
CLOVA_OCR_APIGW_INVOKE_URL=
CLOVA_OCR_SECRET_KEY=

# Storage
STORAGE_PATH=storage

# Celery
CELERY_BROKER_URL=redis://fastapi_ocr-redis:6379/0
```

### 2. Docker Compose로 실행 (권장)

```bash
docker compose up -d
```

구성되는 컨테이너:
- `fastapi_ocr` : API 서버 (호스트 **9093** → 컨테이너 8000)
- `fastapi_ocr-mysql` : MySQL 5.7 (3306)
- `fastapi_ocr-mongodb` : MongoDB (27017)
- `fastapi_ocr-redis` : Redis 7 (6379)
- `fastapi_ocr-celery` : Celery 워커

### 3. 로컬에서 직접 실행 (uv)

```bash
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Celery 워커는 별도 터미널에서:
```bash
uv run celery -A app.celery_worker worker --loglevel=info
```


## 테스트

```bash
uv run pytest                       # 전체
uv run pytest tests/unit             # 단위 테스트만
uv run pytest tests/feature          # 기능 테스트만
```


## 실행 화면

### 샘플 이미지
![샘플 이미지](storage/screenshots/sample.png)

### Naver Clova OCR 추출 결과
![Naver Clova OCR 추출 결과](storage/screenshots/clovaocr.PNG)

### EasyOCR 추출 결과
![EasyOCR 추출 결과](storage/screenshots/easyocr.PNG)

### PaddleOCR 추출 결과
![PaddleOCR 추출 결과](storage/screenshots/paddleocr.PNG)

### Swagger UI
FastAPI가 자동 생성한 문서를 통해 각 엔드포인트의 스키마와 응답 예시를 확인할 수 있습니다.
- Swagger UI: `http://localhost:9093/docs`
- ReDoc: `http://localhost:9093/redoc`

[Notion에서 보기](https://www.notion.so/fastapi-OCR-API-27c4e65ad8338002bb64cf104b0d2edd?source=copy_link)


## 기능 목록

- [x] 멀티 OCR 엔진 지원 (EasyOCR / PaddleOCR / Clova OCR)
- [x] JWT Bearer 기반 엔드포인트 보호
- [x] 비동기 API + 파일 업로드
- [x] 엔진 추상화 모듈화로 OCR 엔진 추가 용이
- [x] 전역 예외 핸들러 및 통일된 에러 응답 포맷
- [x] Celery + Redis 기반 비동기 작업 큐
- [x] SQLAlchemy + aiomysql + Alembic
- [x] Unit / Feature 테스트 구성
- [x] Swagger UI / ReDoc 자동 문서화
