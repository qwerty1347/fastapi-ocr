# 다중 엔진 OCR API

FastAPI 기반 OCR 서비스. EasyOCR · PaddleOCR · Naver Clova OCR 세 엔진을 하나의 인터페이스로 통합하고, 동기 / 비동기 잡 두 가지 처리 모드를 제공합니다.

> 가벼운 단발 요청은 즉시 응답하는 동기 엔드포인트로, 무거운 추론은 Celery 워커가 처리하는 비동기 잡 엔드포인트로 분리해 사용자 응답성과 처리량을 양립시켰습니다. 잡 상태는 MySQL `ocr_jobs` 테이블에 `pending → started → success/failed` 라이프사이클로 영속화되어 외부에서 가시화 가능하고, 엔진은 `BaseEngine` ABC 로 추상화되어 신규 엔진 추가가 클래스 1개로 끝납니다.

---

## 목차

1. [핵심 특징](#핵심-특징)
2. [아키텍처](#아키텍처)
3. [기술 스택](#기술-스택)
4. [프로젝트 구조](#프로젝트-구조)
5. [API 명세](#api-명세)
6. [도메인 상세](#도메인-상세)
7. [비동기 잡 라이프사이클](#비동기-잡-라이프사이클)
8. [Celery 워커 정책](#celery-워커-정책)
9. [남은 제한 사항 & 다음 단계](#남은-제한-사항--다음-단계)

---

## 핵심 특징

| 영역 | 내용 |
|---|---|
| **다중 OCR 엔진** | EasyOCR · PaddleOCR · Clova OCR(HTTP) 을 `BaseEngine` ABC 로 통합. 엔진 추가는 클래스 1개 + 팩토리 등록 한 줄로 끝남 |
| **동기 엔드포인트** | `POST /api/v1/ocr/` — 업로드 즉시 추론하고 결과 반환. 단일 이미지·즉시 응답이 필요한 경로 |
| **비동기 잡 엔드포인트** | `POST /api/v1/ocr/jobs` — 잡 등록 즉시 `job_id` 반환. Celery 워커가 백그라운드에서 처리하고 결과를 MySQL `ocr_jobs` 테이블에 영속화 |
| **잡 라이프사이클 영속화** | `pending → started → success/failed` 상태 전이를 DB에 기록. 영구 가시성 확보 |
| **JWT 인증** | `POST /api/v1/token/` 에서 발급한 access token 으로 모든 OCR 엔드포인트 보호 (`OAuth2PasswordBearer`) |
---

## 아키텍처
![Architecture](storage/screenshots/architecture.png)

---

### 동기 OCR 흐름 (`POST /ocr/`)

```
[Client]                [FastAPI]                [OCR Engine]
   │                       │                          │
   │ POST /api/v1/ocr/     │                          │
   │ (file, engine)        │                          │
   ├──────────────────────►│                          │
   │                       │ JWT verify               │
   │                       │ file validate            │
   │                       │ save temp                │
   │                       │                          │
   │                       │ asyncio.to_thread()      │
   │                       ├─────────────────────────►│
   │                       │   engine.recognize()     │
   │                       │   → result               │
   │                       │◄─────────────────────────┤
   │                       │ delete temp              │
   │                       │                          │
   │ { code, data:{images}}│                          │
   │◄──────────────────────┤                          │
```

> 동기 엔진 호출(EasyOCR · PaddleOCR)은 CPU bound. async 라우터에서 그대로 호출하면 이벤트 루프가 멈추므로 `asyncio.to_thread()` 로 워커 스레드에 위임해 동시 요청 처리 능력을 유지합니다.

---

### 비동기 잡 흐름 (`POST /ocr/jobs`)

```
[Client]            [API]               [MySQL]            [Redis]            [Worker]
   │ POST /jobs       │                    │                  │                  │
   ├─────────────────►│                    │                  │                  │
   │                  │ INSERT pending     │                  │                  │
   │                  ├───────────────────►│                  │                  │
   │                  │ enqueue run_ocr    │                  │                  │
   │                  ├──────────────────────────────────────►│                  │
   │ 202 {job_id}     │                    │                  │ pull             │
   │◄─────────────────┤                    │                  ├─────────────────►│
   │                  │                    │ UPDATE started   │                  │
   │                  │                    │◄─────────────────────────────────── │
   │                  │                    │                  │  do OCR (3~30s)  │
   │                  │                    │ UPDATE success   │                  │
   │                  │                    │◄─────────────────────────────────── │
   │ GET /jobs/{id}   │                    │                  │                  │
   ├─────────────────►│ SELECT             │                  │                  │
   │                  ├───────────────────►│                  │                  │
   │ {status, result} │                    │                  │                  │
   │◄─────────────────┤                    │                  │                  │
```

---

### 모듈 추상화 — OCR 엔진

```
app/services/ocr/module.py
        ┌───────────────────────────┐
        │  OcrModule                │
        │   OCR_ENGINES = {         │
        │     "easyocr": EasyOcr,   │
        │     "paddleocr": PaddleOcr│
        │     "clovaocr": ClovaOcr, │
        │   }                       │
        └──────────┬────────────────┘
                   │ creates on first use
                   ▼
        ┌───────────────────────────┐
        │   BaseEngine (ABC)        │
        │   recognize(file_path)    │
        │   convert_to_json(result) │
        └──────────┬────────────────┘
                   │
        ┌──────────┼──────────┬──────────┐
        ▼          ▼          ▼          ▼
        EasyOcr   PaddleOcr   ClovaOcr   (신규 엔진)
```

엔진은 모두 **sync 메서드**(`recognize(file_path: Path)`)로 통일. API 에서는 `asyncio.to_thread` 로 감싸 이벤트 루프 블로킹을 회피하고, 워커에서는 직접 호출합니다.

---

## 기술 스택

### Runtime
- **Python** 3.11+
- **FastAPI** 0.135.3
- **Uvicorn[standard]** 0.44.0 (uvloop, httptools, watchfiles)
- **Pydantic** 2.13.0 / **pydantic-settings** 2.13.1
- **python-multipart** (multipart/form-data)

### OCR 엔진
- **EasyOCR** 1.7.2 (PyTorch 기반)
- **PaddleOCR** 2.9.1 + **paddlepaddle** 2.6.2 (PaddlePaddle 기반)
- **Naver Clova OCR** (HTTP API, `httpx` 로 호출)

### 작업 큐
- **Celery** 5.6.3
- **Redis** 7.4.0 (broker + result backend)
- **Flower** 2.0.1

### 데이터베이스
- **MySQL** 5.7 (utf8mb4)
- **SQLAlchemy** 2.0.49 + **aiomysql** 0.3.2 (async) + **pymysql** 1.1.2 (sync)
- **Alembic** 1.18.4 (마이그레이션)

### Auth
- **python-jose[cryptography]** (JWT HS256)

### Dev / 노트북
- **Jupyter Notebook** 7.5.5 + **ipywidgets** 8.1.8
- **pytest** 9.0.3 + **pytest-asyncio** 1.3.0
- **uv** (`uv.lock` 기반 재현 가능한 설치)

---

## 프로젝트 구조

```text
fastapi-ocr/
├── .docker/
│   ├── Dockerfile                       # python:3.11 + libgl1 + uv sync --frozen
│   └── entrypoint.sh                    # SERVICE_TYPE 분기 (app | worker | flower)
├── app/
│   ├── api/
│   │   ├── __init__.py                  # /api 루트 + pkgutil 자동 수집
│   │   └── v1/
│   │       ├── ocr/
│   │       │   ├── __init__.py
│   │       │   └── router.py            # POST /ocr/, POST /ocr/jobs, GET /ocr/jobs/{id}
│   │       └── token/
│   │           ├── __init__.py
│   │           └── router.py            # POST /token/
│   ├── core/
│   │   ├── celery.py                    # celery app re-export
│   │   ├── config.py                    # pydantic-settings (.env 로더), BASE_DIR, STORAGE_PATH
│   │   ├── logging.py                   # setup_logging
│   │   ├── dependencies/
│   │   │   ├── auth.py                  # verify_access_token (OAuth2PasswordBearer)
│   │   │   ├── database.py              # get_database (AsyncSession)
│   │   │   ├── file.py                  # get_ocr_validated_file
│   │   │   └── ocr.py                   # get_ocr_service / get_ocr_job_service / get_ocr_repository
│   │   ├── exceptions/
│   │   │   ├── custom.py                # BusinessException
│   │   │   └── handlers.py              # 전역 예외 → 통일 응답 봉투
│   │   └── utils/
│   │       ├── file.py                  # save_file / delete_file / 확장자 검증
│   │       ├── http_client.py           # httpx wrapper
│   │       └── response.py              # success_response / error_response
│   ├── infrastructure/
│   │   └── database/
│   │       └── session.py               # async/sync 엔진 + 세션 팩토리
│   ├── models/
│   │   ├── base.py                      # 공용 declarative Base
│   │   ├── __init__.py                  # 모델 re-export (alembic autogenerate용)
│   │   └── ocr_job.py                   # OcrJob 모델 + JobStatus enum
│   ├── module/
│   │   └── ocr/
│   │       ├── base.py                  # BaseEngine ABC
│   │       ├── easyocr.py
│   │       ├── paddleocr.py
│   │       └── clovaocr.py              # httpx 로 Clova API 호출
│   ├── repositories/
│   │   └── ocr.py                       # OcrRepository (async DB 접근)
│   ├── schemas/
│   │   ├── base.py                      # SuccessResponse / ErrorResponse
│   │   ├── enums.py                     # OcrEngine
│   │   ├── ocr/
│   │   │   ├── request.py               # OcrRequest
│   │   │   └── response.py              # OcrResponse
│   │   └── token/
│   │       └── response.py              # TokenResponse
│   ├── services/
│   │   ├── auth/
│   │   │   └── jwt.py                   # access token 발급/검증
│   │   └── ocr/
│   │       ├── module.py                # OcrModule (엔진 팩토리)
│   │       ├── ocr.py                   # OcrService (동기 엔드포인트용)
│   │       └── job.py                   # OcrJobService (비동기 잡 등록)
│   ├── worker/
│   │   ├── celery_app.py                # Celery 앱 (queue: ocr, default)
│   │   └── tasks/
│   │       ├── __init__.py
│   │       ├── ocr.py                   # run_ocr 태스크
│   │       └── test.py
│   └── main.py                          # FastAPI 진입점 (lifespan, 예외 핸들러 등록)
├── migrations/
│   ├── env.py                           # target_metadata = Base.metadata
│   └── versions/                        # alembic 리비전
├── storage/
│   ├── screenshots/                     # README 첨부 이미지
│   └── uploads/ocr/                     # 업로드 파일 임시 저장
├── notebooks/                           # Jupyter 탐색 노트북
├── tests/
│   ├── feature/ocr/
│   └── unit/ocr/
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── pytest.ini
└── README.md
```

---

## API 명세

모든 OCR 엔드포인트는 `/api/v1` 프리픽스 아래에 있고, `Authorization: Bearer <token>` 필요합니다.

### 토큰 발급

| Method | Path | 설명 |
|---|---|---|
| `POST` | `/api/v1/token/` | JWT access token 발급 (public) |

**응답** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

### 동기 OCR

| Method | Path | 설명 |
|---|---|---|
| `POST` | `/api/v1/ocr/` | 업로드 즉시 추론 후 결과 반환 |

**요청** (`multipart/form-data`):
- `file`: 이미지 파일 (`jpg` / `jpeg` / `png` / `pdf`)
- `engine`: `easyocr` / `paddleocr` / `clovaocr`

**응답** (200):
```json
{
  "code": "200",
  "data": {
    "images": [
      {
        "boundingPoly": [[12, 18], [230, 18], [230, 52], [12, 52]],
        "text": "INVOICE",
        "confidence": 0.987
      }
    ]
  }
}
```

### 비동기 잡 등록

| Method | Path | 설명 |
|---|---|---|
| `POST` | `/api/v1/ocr/jobs` | 잡 등록 → `job_id` 반환, Celery 워커가 백그라운드 처리 |
| `GET` | `/api/v1/ocr/jobs/{id}` | 잡 상태/결과 조회 |

**요청** (`POST /jobs`):
- `file` + `engine` (동기와 동일)

**응답** (202, 목표 형태):
```json
{
  "code": "202",
  "data": {
    "job_id": "5f3c...uuid4",
    "status": "pending"
  }
}
```

**상태 조회 응답** (목표 형태):
```json
{
  "code": "200",
  "data": {
    "job_id": "5f3c...uuid4",
    "status": "success",
    "engine": "paddleocr",
    "result": { "images": [...] },
    "created_at": "2026-06-08T10:00:00",
    "started_at": "2026-06-08T10:00:02",
    "finished_at": "2026-06-08T10:00:18"
  }
}
```

**에러 응답** (401 / 422):
```json
{
  "code": 422,
  "message": "Validation Error",
  "errors": [...]
}
```

---

## 도메인 상세

### 1) OCR 엔진 추상화 (`app/module/ocr/`)

`BaseEngine` ABC 가 모든 엔진의 계약을 정의:

```python
class BaseEngine(ABC):
    @abstractmethod
    def recognize(self, file_path: Path) -> dict: ...

    @abstractmethod
    def convert_to_json(self, raw) -> dict: ...
```

각 엔진은 추론 결과를 통일된 JSON 으로 변환해 반환합니다. 신규 엔진 추가 시:

1. `app/module/ocr/<engine>.py` 에 `BaseEngine` 상속한 클래스 작성
2. `app/services/ocr/module.py` 의 `OCR_ENGINES` 딕셔너리에 등록
3. `app/schemas/enums.py` 의 `OcrEngine` 에 값 추가

### 2) 동기 처리 서비스 (`OcrService`)

`POST /ocr/` 에서 호출. 핵심 동작:

1. JWT 검증 + 파일 확장자/사이즈 검증 (의존성 주입)
2. 업로드 파일을 `storage/uploads/ocr/` 에 임시 저장
3. `OcrModule(engine).recognize(file_path)` 를 `asyncio.to_thread()` 로 래핑해 호출
4. 결과 JSON 반환
5. 임시 파일 정리

> EasyOCR · PaddleOCR 은 PyTorch / PaddlePaddle 기반 sync 호출. async 라우터에서 직접 호출하면 이벤트 루프가 멈추므로 워커 스레드 격리 필요.

### 3) 비동기 잡 서비스 (`OcrJobService`)

`POST /ocr/jobs` 에서 호출. 핵심 동작:

1. 업로드 파일을 영구 경로에 저장 (워커가 접근해야 하므로)
2. `OcrRepository.create_ocr_job()` 으로 `ocr_jobs` row INSERT (`pending`)
3. `run_ocr.delay(job_id)` 로 Celery 에 enqueue
4. `job_id` 반환 → 클라이언트는 `GET /jobs/{id}` 로 폴링

### 4) Celery 워커 (`app/worker/tasks/ocr.py`)

`run_ocr(job_id)` 태스크가 실제 추론을 수행:

```python
@celery.task
def run_ocr(job_id: str):
    with sync_session_factory() as session:
        ocr_job = session.get(OcrJob, job_id)
        if ocr_job is None:
            return

        ocr_job.status = JobStatus.STARTED
        ocr_job.started_at = func.now()
        session.commit()   # ← 즉시 commit 으로 외부 가시성 확보

        try:
            # OcrModule(ocr_job.engine).recognize(Path(ocr_job.file_path))
            pass
        except Exception as e:
            ocr_job.status = JobStatus.FAILED
            ocr_job.info = {"error": str(e)}
            ocr_job.finished_at = func.now()
            session.commit()
        else:
            ocr_job.status = JobStatus.SUCCESS
            # ocr_job.result = ...
            ocr_job.finished_at = func.now()
            session.commit()
```

`STARTED` 즉시 commit → 추론(try) → SUCCESS/FAILED commit 분리는 **외부 가시성** 과 **실패 추적** 을 동시에 잡기 위함입니다.

### 5) 이중 DB 세션 (`infrastructure/database/session.py`)

- **FastAPI 라우터**: `aiomysql` 기반 `AsyncSession` (논블로킹)
- **Celery 워커 + Alembic**: `pymysql` 기반 `Session` (동기, 워커 컨텍스트에서 안전)

`pool_pre_ping` + `pool_recycle` 로 MySQL `wait_timeout` 끊김을 자동 회복하고, 동기/비동기 양쪽이 같은 MySQL 인스턴스를 공유하되 컨텍스트별 최적 드라이버를 사용합니다.

### 6) 전역 예외 → 통일 응답 봉투 (`exceptions/handlers.py`)

`HTTPException` · `RequestValidationError` · `JWTError` · `BusinessException` · 그 외 모든 `Exception` 이 `{code, message, errors[]}` 봉투로 정규화됩니다. 라우터/서비스 레이어는 비즈니스 예외만 던지면 끝.

---

## 비동기 잡 라이프사이클

`ocr_jobs` 테이블의 status 컬럼이 잡의 단일 진실 소스입니다.

```
   ┌──────────┐
   │ pending  │ ← API 가 INSERT (잡 등록 시점)
   └────┬─────┘
        │ 워커가 pull + commit
        ▼
   ┌──────────┐
   │ started  │ ← 워커가 추론 시작 직전 즉시 commit (외부 가시성)
   └────┬─────┘
        │
        ▼
   ┌──────────┐         ┌──────────┐
   │ success  │   or    │  failed  │
   │ + result │         │ + info   │
   └──────────┘         └──────────┘
        ↑                    ↑
        │                    │
        └─ 추론 정상 종료      └─ 예외 발생 (워커가 잡아 기록)
```

### 멱등성 보장

- `job_id` 기반 SELECT → UPDATE 흐름이므로 같은 잡이 두 번 실행되어도 같은 row 를 갱신만 함
- `task_acks_late=True` + `task_reject_on_worker_lost=True` 가 워커 장애 시 재할당을 보장
- 재실행되더라도 중복 사이드이펙트 없음 (멱등)

### Flower 모니터링과의 차이

| | Flower (Celery in-memory) | `ocr_jobs` 테이블 |
|---|---|---|
| 보존 | Redis result_expires (기본 24h) | 영구 |
| 가시성 | PENDING / STARTED / SUCCESS / FAILED | + engine, file_path, result, info, timestamps |
| 외부 시스템 | Celery 종속 | SQL 로 직접 조회 가능 |
| 용도 | 운영 모니터링·디버깅 | 비즈니스 데이터·통계 |

---

## Celery 워커 정책

`app/worker/celery_app.py` 의 핵심 설정:

```python
celery.conf.update(
    worker_prefetch_multiplier=1,            # 무거운 OCR 은 한 번에 1개만 선점
    task_acks_late=True,                     # 잡 끝난 뒤 ack → 워커 장애 시 재할당
    task_reject_on_worker_lost=True,         # 워커 사망 시 명시적 reject
    task_time_limit=60 * 5,                  # hard 5분
    task_soft_time_limit=60 * 4,             # soft 4분 (cleanup 기회)
    worker_max_tasks_per_child=200,          # 200개마다 자식 재시작 (모델 메모리 누수 방어)
    task_track_started=True,                 # PENDING ↔ STARTED 구분
    task_serializer="json",
    result_serializer="json",
    timezone="Asia/Seoul",
)
```

### 정책별 의도

| 정책 | 왜 이렇게 |
|---|---|
| `worker_prefetch_multiplier=1` | 기본값 4 는 무거운 OCR 추론에서 한 워커가 4개를 선점해 다른 워커가 놀게 됨. 1로 두면 사용 가능한 워커에 골고루 분배 |
| `acks_late` + `reject_on_worker_lost` | SIGKILL · OOM 으로 워커가 죽어도 broker 가 같은 잡을 다른 워커에 재할당. 잡이 멱등하므로 안전 |
| `task_time_limit=300` | OCR 한 장은 보통 5~30초. 5분이면 충분히 여유. 멈춘 잡이 워커를 영구 점유하는 사고 차단 |
| `task_soft_time_limit=240` | hard 보다 1분 짧게. soft 초과 시 `SoftTimeLimitExceeded` 예외 → 임시 파일 cleanup 가능 |
| `worker_max_tasks_per_child=200` | PaddleOCR / EasyOCR 은 모델을 메모리에 들고 있어 장시간 누수 가능. 200 잡마다 자식 재시작으로 RSS 안정 |
| `task_track_started=True` | Flower 에서 PENDING(대기) ↔ STARTED(실행중) 구분. 디버깅·모니터링에 유리 |

---

## 남은 제한 사항 & 다음 단계

### 현재 제한 사항

| 항목 | 상태 | 설명 |
|---|---|---|
| **`run_ocr` 태스크 본체** | ❌ | `app/worker/tasks/ocr.py` 의 try 블록이 `pass`. STARTED 갱신만 동작하고 실제 엔진 호출 부재 |
| **`GET /jobs/{id}` 미구현** | ❌ | 라우터가 `pass`. `OcrJobResponse` 스키마도 없음 |
| **`POST /jobs` 응답 임시값** | ⚠️ | 현재 `{"message": "test"}` 반환. `202 {job_id, status}` 형태로 정리 필요 |
| **`OcrModule.OCR_ENGINES` 가 eager** | ⚠️ | 클래스 본문에서 세 엔진 모두 즉시 인스턴스화 → 임포트만으로 EasyOCR / PaddleOCR 메모리 적재. lazy 팩토리(`_FACTORIES = {key: class}`)로 전환 권장 |
| **`BaseEngine.recognize` 시그니처 불일치** | ⚠️ | ABC 는 `recognize(file_path: Path)` 인데 `EasyOcr.recognize(file: UploadFile)` 로 받음. 추상 계약 위반 → `Path` 로 통일 필요 |
| **`OcrRepository.create_ocr_job` 의 트랜잭션 경계** | ⚠️ | `db.add` 후 호출 측에서 commit. 책임 경계 모호 — 서비스 레이어에 명시하거나 UoW 패턴 도입 검토 |
| **테스트 커버리지** | ⚠️ | `tests/` 디렉터리 구조만 있고 실질 커버리지는 미흡 |
| **MongoDB** | ❌ | docker-compose 에 정의되어 있지만 현재 미사용 |

### 권장 다음 단계

1. **`run_ocr` 본체 구현**: `OcrModule(engine).recognize(Path(file_path))` 호출 + 결과 직렬화 + `ocr_job.result` 저장
2. **`GET /jobs/{id}` 구현**: `OcrJobResponse` 스키마 정의 + `OcrRepository.get_ocr_job(id)` 추가 + 상태별 응답 분기
3. **`POST /jobs` 응답 정리**: `202 {job_id, status: "pending"}` 표준화 + `OcrJobCreateResponse` 스키마 추가
4. **`OcrModule` lazy 전환**: `OCR_ENGINES = {key: class}` 로 바꾸고 `__init__` 첫 호출 시 인스턴스화 → 워커/앱 부팅 비용 절감
5. **`BaseEngine` 시그니처 통일**: 모든 엔진을 `recognize(file_path: Path)` 로 맞추고, 라우터/서비스에서 임시 저장 후 Path 전달
6. **트랜잭션 책임 명시**: 레포지토리는 변경만, 서비스가 트랜잭션 경계 (commit/rollback) 책임지는 UoW 패턴 적용
7. **테스트 보강**: 라우터·서비스 단위 테스트 (`app.dependency_overrides` 활용) + 워커 태스크는 mock OCR 엔진으로 검증
8. **잡 retry 정책 정교화**: Clova API 5xx / 429 / Timeout 등 특정 예외만 선별 재시도 (`autoretry_for` + 지수 백오프 + 지터)
9. **임시 파일 정리 배치**: 24시간 경과 업로드 파일 삭제 + 잡 보존 기간 정책. `celery beat` 로 스케줄

---

## 실행 화면

### 샘플 이미지
![샘플 이미지](storage/screenshots/sample.png)

### 추출 결과 비교

#### Naver Clova OCR
![Clova](storage/screenshots/clovaocr.PNG)

#### EasyOCR
![Easy](storage/screenshots/easyocr.PNG)

#### PaddleOCR
![Paddle](storage/screenshots/paddleocr.PNG)