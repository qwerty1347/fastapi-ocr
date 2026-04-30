# 비동기 OCR (Celery + DB Job 추적) 구현 가이드

## 개요

기존 `POST /api/v1/ocr/`는 **동기** 처리 — 요청을 받아 OCR이 끝날 때까지 응답을 기다립니다. PaddleOCR/EasyOCR 추론은 수 초~수십 초가 걸려 클라이언트가 타임아웃되거나 워커가 점유됩니다.

비동기 버전 흐름:

1. 클라이언트가 이미지 업로드 → `POST /api/v1/ocr/jobs`
2. API가 즉시 `OcrJob` row INSERT(`status=pending`) + Celery 큐에 enqueue
3. Celery 워커가 OCR 실행 → `started → success/failed` 상태 갱신 + 결과 저장
4. 클라이언트가 `GET /api/v1/ocr/jobs/{id}`로 상태/결과 조회

---

## 1. 데이터 모델

### 1-1. 공용 `Base`

모델마다 `declarative_base()`를 새로 호출하면 metadata가 갈라져 alembic autogenerate가 일부 테이블을 놓칩니다. **한 군데에 공용 Base**를 두고 모든 모델이 이를 상속.

```python
# app/models/base.py
from sqlalchemy.orm import declarative_base

Base = declarative_base()
```

### 1-2. `OcrJob` 테이블

```python
# app/models/ocr_job.py
import enum

from sqlalchemy import JSON, Column, DateTime, Enum, String, func
from app.models.base import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"      # 큐에 들어갔지만 아직 시작 안 됨
    STARTED = "started"      # 워커가 실행 중
    SUCCESS = "success"      # 정상 완료
    FAILED = "failed"        # 예외/타임아웃


class OcrJob(Base):
    __tablename__: str = "ocr_jobs"

    id = Column(String(50), primary_key=True, comment="UUID4")
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True,
                    comment="OCR 상태: pending | started | success | failed")
    engine = Column(String(30), nullable=False, comment="OCR 엔진: easyocr | paddleocr | clovaocr")
    file_name = Column(String(255), nullable=False, comment="업로드 파일명")
    file_path = Column(String(512), nullable=False, comment="업로드 파일 경로")
    result = Column(JSON, nullable=True, comment="OCR 완료 결과")
    info = Column(JSON, nullable=True, comment="OCR 실패 시 메시지, 로그")
    created_at = Column(DateTime, default=func.now(), comment="생성 시간")
    started_at = Column(DateTime, nullable=True, comment="실행 시간")
    finished_at = Column(DateTime, nullable=True, comment="완료 시간")
```

### 1-3. 모델 패키지 export

`models/__init__.py`에서 **SQLAlchemy 모델 클래스**(여기선 `OcrJob`)를 한 번 import 해두면, alembic env.py에서는 `from app import models` 한 줄로 모든 모델이 `Base.metadata`에 등록됩니다.

```python
# app/models/__init__.py
from app.models.ocr_job import JobStatus, OcrJob

__all__ = ["JobStatus", "OcrJob"]
```

> **`OcrJob`** — `Base`를 상속한 SQLAlchemy 모델. 이게 import되어야 `Base.metadata`에 테이블이 등록되고 alembic autogenerate가 인식.
>
> **`JobStatus`** — 단순 Python `Enum`이라 metadata 등록과 **무관**. alembic 입장에선 굳이 export할 필요가 없지만, 다른 모듈에서 `from app.models import JobStatus`로 짧게 쓸 수 있도록 **편의를 위한 re-export**일 뿐. 빼도 alembic에는 영향 없음.
>
> 모델이 늘어나면 새 모델 클래스만 한 줄씩 추가하면 됨 (Enum/스칼라 타입은 선택).

### 1-4. 세션 및 엔진

FastAPI는 **async**, Celery 워커는 **sync**로 같은 DB에 접속합니다. 드라이버가 다르므로 엔진/세션 팩토리를 두 벌 만듭니다.

#### 드라이버 패키지 (MySQL 8+ 경우)

```bash
uv add aiomysql pymysql cryptography
```

- `aiomysql` — async (FastAPI)
- `pymysql` — sync (Celery, alembic)
- `cryptography` — `mysql_native_password` 사용 시 필요

#### 세션 팩토리

```python
# app/infrastructure/database/session.py
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import config


def _build_url(driver: str) -> str:
    return (
        f"mysql+{driver}://{config.DB_USERNAME}:{config.DB_PASSWORD}"
        f"@{config.DB_HOST}:{config.DB_PORT}/{config.DB_DATABASE}"
        f"?charset=utf8mb4"
    )


SYNC_DATABASE_URL = _build_url("pymysql")
ASYNC_DATABASE_URL = _build_url("aiomysql")

# === Async (FastAPI) ===
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,     # 끊긴 커넥션 자동 회복
    pool_recycle=3600,      # MySQL wait_timeout보다 짧게
    pool_size=10,
    max_overflow=20,
)
async_session_factory = async_sessionmaker(
    async_engine,
    expire_on_commit=False,
    autoflush=False,
)

# === Sync (Celery 워커, alembic) ===
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10,
)
sync_session_factory = sessionmaker(
    sync_engine,
    expire_on_commit=False,
    autoflush=False,
)
```

#### 사용 예

**FastAPI 의존성 (async):**
```python
# app/core/dependencies/database.py
from app.infrastructure.database.session import async_session_factory


async def get_database():
    async with async_session_factory() as session:
        yield session
```

**Celery 태스크 (sync):**
```python
from app.infrastructure.database.session import sync_session_factory

with sync_session_factory() as session:
    ...  # session.get(...), session.commit()
```

> **`pool_pre_ping=True`** — 매 체크아웃마다 ping을 보내 죽은 커넥션을 거름. 약간의 오버헤드가 있지만 MySQL의 `wait_timeout`(기본 8h)이나 도커 재시작으로 끊긴 커넥션을 안전하게 회복합니다. OCR처럼 작업 간 텀이 긴 워커에서 특히 유용.

### 1-5. Alembic env.py 설정

`migrations/env.py`의 `target_metadata`가 `None`이면 autogenerate가 빈 마이그레이션을 만듭니다. `Base.metadata`로 교체하고, 모델 패키지를 import 해 등록.

```python
# migrations/env.py (수정 부분)
from app.models.base import Base
from app import models  # noqa: F401  (모델 등록)

target_metadata = Base.metadata
```

### 1-6. Alembic 마이그레이션

```bash
docker compose exec app uv run alembic revision --autogenerate -m "add ocr_jobs"
docker compose exec app uv run alembic upgrade head
```

> 자동생성된 `migrations/versions/*.py`는 **반드시 한 번 검토** — MySQL dialect에서 `Enum`/`JSON`/`comment`가 의도대로 잡혔는지, 의도하지 않은 drop이 없는지 확인.

확인:
```bash
docker compose exec mysql mysql -uroot -proot fastapi -e "DESC ocr_jobs;"
```

---

## 2. 저장소(Repository)

DB 접근은 라우터/서비스에서 직접 하지 말고 리포지토리 한 곳에서. 현재 구현은 최소한의 `create_ocr_job`만 있음 — 잡 조회/상태 갱신은 워커 쪽이 sync 세션으로 직접 처리하기 때문.

```python
# app/repositories/ocr.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr_job import OcrJob


class OcrRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_ocr_job(self, ocr_job: OcrJob):
        self.db.add(ocr_job)
        return ocr_job
```

> **commit/refresh는 호출 측이 책임** — 서비스 계층(`OcrJobService.create_ocr_job`)이 `db.commit()`을 직접 호출. 향후 read 메서드(`get`)나 status 갱신을 추가할 경우 동일 패턴.

---

## 3. 서비스 계층 — 잡 등록

API에서 호출되는 비동기 잡 등록 서비스.

```python
# app/services/ocr/job.py
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.file import save_file
from app.models.ocr_job import OcrJob
from app.repositories.ocr import OcrRepository
from app.worker.tasks.ocr import run_ocr


class OcrJobService:
    def __init__(self, db: AsyncSession, ocr_repository: OcrRepository):
        self.db = db
        self.ocr_repository = ocr_repository

    async def create_ocr_job(self, file: UploadFile, engine: str) -> OcrJob:
        job = OcrJob(
            id=str(uuid4()),
            engine=engine,
            file_name=file.filename,
            file_path=str(await save_file(file)),
        )
        ocr_job = await self.ocr_repository.create_ocr_job(job)
        await self.db.commit()              # 워커가 row 조회할 수 있도록 먼저 commit
        run_ocr.delay(ocr_job.id)           # 그 다음 enqueue (순서 중요)
        return ocr_job
```

### 핵심 포인트

- **`commit()` → `delay()` 순서 필수** — 워커가 broker에서 메시지를 pull한 직후 DB에서 `session.get(OcrJob, id)`로 조회합니다. commit 전에 enqueue하면 워커가 row를 못 찾는 race가 발생.
- **`save_file()`은 await 필수** — `app/core/utils/file.py`의 `save_file`은 `async def`. await 없이 호출하면 코루틴 객체의 repr 문자열이 그대로 `file_path`에 들어갑니다.

### 의존성 주입 — 단일 db 세션 공유

```python
# app/core/dependencies/ocr.py
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies.database import get_database
from app.repositories.ocr import OcrRepository
from app.services.ocr.job import OcrJobService


def get_ocr_job_service(db: AsyncSession = Depends(get_database)) -> OcrJobService:
    return OcrJobService(db, OcrRepository(db))
```

> 서비스와 repository가 **동일한 `AsyncSession` 인스턴스**를 공유 → 마지막에 `self.db.commit()` 한 번으로 전체 트랜잭션 커밋. 다른 repository를 추가할 땐 동일하게 `OtherRepository(db)`를 함께 넘기면 됨.

---

## 4. Celery 태스크

### 4-1. 큐 설정

```python
# app/worker/celery_app.py
celery.conf.task_queues = {"ocr": {}, "default": {}}
celery.conf.task_default_queue = "ocr"

celery.conf.update(
    worker_prefetch_multiplier=1,    # 무거운 OCR은 1
    task_acks_late=True,             # 워커 죽어도 재처리 (job_id가 결정적이라 멱등)
    task_reject_on_worker_lost=True,
    task_time_limit=60 * 5,          # hard 5분
    task_soft_time_limit=60 * 4,     # soft 4분
    task_track_started=True,         # STARTED 상태 추적
    result_expires=60 * 60 * 24,
    worker_max_tasks_per_child=200,  # OCR 모델 메모리 누수 방지
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Seoul",
    enable_utc=False,
)
```

### 4-2. OCR 태스크 본체

```python
# app/worker/tasks/ocr.py
from sqlalchemy import func

from app.infrastructure.database.session import sync_session_factory
from app.models.ocr_job import JobStatus, OcrJob
from app.worker.celery_app import celery


@celery.task
def run_ocr(job_id: str):
    with sync_session_factory() as session:
        ocr_job = session.get(OcrJob, job_id)
        if ocr_job is None:
            return

        # STARTED — 즉시 commit 해서 외부 가시성 확보
        ocr_job.status = JobStatus.STARTED
        ocr_job.started_at = func.now()
        session.commit()

        try:
            # TODO: 실제 OCR 추론
            # engine = OcrModule(ocr_job.engine).engine
            # result = engine.recognize(Path(ocr_job.file_path))
            result = ...
        except Exception as e:
            ocr_job.status = JobStatus.FAILED
            ocr_job.info = {"error": str(e)}
            ocr_job.finished_at = func.now()
            session.commit()
            raise   # Celery에 FAILED 전달
        else:
            ocr_job.status = JobStatus.SUCCESS
            ocr_job.result = result
            ocr_job.finished_at = func.now()
            session.commit()
```

### 핵심 원칙

1. **STARTED 표시는 즉시 commit** — 외부에서 `GET /jobs/{id}` 조회 시 진행 중임이 즉시 보임. 워커가 SIGKILL로 죽어도 좀비 탐지 가능.
2. **try는 OCR 추론 부분만 감싸기** — `session.get()`이나 첫 commit 실패는 인프라 문제라 잡을 FAILED로 기록할 의미가 없음. 추론 단계만 보호.
3. **except에서 반드시 commit** — 안 하면 잡이 영원히 STARTED로 남아 좀비. DB에 FAILED 흔적을 남기고 → `raise`로 Celery에 알림.
4. **`raise`로 재전파** — Celery는 예외가 새어 나와야 태스크를 FAILED로 인식. 안 던지면 DB는 FAILED인데 Flower는 SUCCESS로 표시되는 불일치 발생.
5. **`else`에 성공 처리 분리** — try 본문에 성공 commit까지 넣으면 commit 자체에서 발생한 예외가 except에 잡혀 상태가 꼬임.
6. **`finally`는 불필요** — `with sync_session_factory()`가 세션 close를 보장.

### 시간 컬럼 — Python 대신 DB 함수

`func.now()`(SQLAlchemy)를 쓰면 MySQL `NOW()`가 호출되어 **DB 서버의 타임존**(컨테이너에서 Asia/Seoul 설정)을 따릅니다. `created_at`이 이미 `func.now()` 기본값을 쓰므로 `started_at`/`finished_at`도 통일.

> Python 쪽에서 직접 채우려면 `datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)`. `datetime.utcnow()`는 Python 3.12+에서 deprecated.

---

## 5. API — 비동기 엔드포인트

기존 `POST /ocr/` (동기)는 그대로 두고, 잡 등록 + 조회 엔드포인트 2개 추가.

### 5-1. 잡 생성 (구현됨)

```python
# app/api/v1/ocr/router.py
from fastapi import status
from fastapi.responses import JSONResponse


@router.post('/jobs', status_code=status.HTTP_202_ACCEPTED)
async def create_ocr_job(
    file: UploadFile = Depends(get_ocr_validated_file),
    ocr_dto: OcrRequest = Depends(parse_ocr_request),
    ocr_job_service: OcrJobService = Depends(get_ocr_job_service),
):
    ocr_job = await ocr_job_service.create_ocr_job(file, ocr_dto.engine.value)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"job_id": ocr_job.id, "status": ocr_job.status.value},
    )
```

### 5-2. 잡 상태/결과 조회 (TODO)

```python
@router.get('/jobs/{id}')
async def get_ocr_job_result():
    pass
```

#### 권장 구현

```python
from app.core.exceptions.custom import BusinessException


@router.get('/jobs/{job_id}')
async def get_ocr_job_result(
    job_id: str,
    db: AsyncSession = Depends(get_database),
):
    ocr_job = await db.get(OcrJob, job_id)
    if ocr_job is None:
        raise BusinessException(code=404, message="job not found")

    return {
        "job_id": ocr_job.id,
        "status": ocr_job.status.value,
        "engine": ocr_job.engine,
        "file_name": ocr_job.file_name,
        "result": ocr_job.result,
        "info": ocr_job.info,
        "created_at": ocr_job.created_at,
        "started_at": ocr_job.started_at,
        "finished_at": ocr_job.finished_at,
    }
```

> 또는 Pydantic 스키마(`app/schemas/ocr/job.py`)를 만들고 `response_model`로 직렬화.

### 5-3. 응답 스키마 (TODO)

현재 `app/schemas/ocr/`엔 `request.py`/`response.py`만 있고 잡 전용 스키마가 없습니다. 추가 권장:

```python
# app/schemas/ocr/job.py
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.models.ocr_job import JobStatus


class OcrJobCreated(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING


class OcrJobResult(BaseModel):
    job_id: str
    status: JobStatus
    engine: str
    file_name: str
    result: Optional[Any] = None
    info: Optional[Any] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
```

---

## 6. 흐름 요약

### 잡 등록 → 즉시 응답

```
client                FastAPI                 MySQL              Redis(broker)         Celery worker
  │  POST /ocr/jobs    │                       │                       │                       │
  ├────────────────────▶                       │                       │                       │
  │                    │  INSERT ocr_job       │                       │                       │
  │                    ├──────────────────────▶│                       │                       │
  │                    │  COMMIT                                       │                       │
  │                    ├──────────────────────▶│                       │                       │
  │                    │  enqueue run_ocr      │                       │                       │
  │                    ├──────────────────────────────────────────────▶│                       │
  │ 202 {job_id}       │                       │                       │  pull task            │
  │◀───────────────────┤                       │                       ├──────────────────────▶│
```

### 워커가 처리

```
worker             MySQL              OCR engine
  │  session.get(OcrJob, job_id)
  ├──────────────────▶
  │  UPDATE status=STARTED, started_at; COMMIT
  ├──────────────────▶
  │  do OCR (3~30s)
  ├────────────────────────────────────▶
  │  result
  │◀───────────────────────────────────┤
  │  UPDATE status=SUCCESS, result, finished_at; COMMIT
  ├──────────────────▶
```

### 클라이언트 폴링

```
client          FastAPI         MySQL
  │ GET /ocr/jobs/{id}   │              │
  ├─────────────────────▶│  SELECT      │
  │                      ├─────────────▶│
  │                      │  pending|started|success|failed
  │ 200 {status,result}  │              │
  │◀─────────────────────┤              │
```

---

## 7. 현재 구현 상태 (체크리스트)

### Phase 1 — 인프라 ✅
- [x] `app/models/base.py` — 공용 `Base = declarative_base()`
- [x] `app/models/ocr_job.py` — `OcrJob` 모델 + `JobStatus` enum
- [x] `app/models/__init__.py` — re-export
- [x] `app/core/config.py` — `DB_*` 필드
- [x] 드라이버 설치 — aiomysql, pymysql
- [x] `app/infrastructure/database/session.py` — async/sync 엔진 + 세션 팩토리
- [x] `migrations/env.py` — `target_metadata = Base.metadata`
- [x] Alembic 마이그레이션 적용

### Phase 2 — 도메인 로직 ✅ (부분)
- [x] `app/repositories/ocr.py` — `OcrRepository.create_ocr_job` (async, FastAPI용)
- [ ] `OcrRepository.get` / `update_status` — 필요 시 추가
- [x] `app/services/ocr/job.py` — `OcrJobService.create_ocr_job` + Celery enqueue
- [ ] `app/schemas/ocr/job.py` — `OcrJobCreated`, `OcrJobResult` 스키마

### Phase 3 — Celery ✅
- [x] `app/worker/celery_app.py` 큐 설정 (queue: `ocr`, prefetch=1, time_limit 등)
- [x] `app/worker/tasks/ocr.py` — `run_ocr` 골격 (status 전이 + try/except/else)
- [ ] **실제 OCR 추론 호출** — `OcrModule(engine).engine.recognize(Path(file_path))` 연결

### Phase 4 — API ✅ (부분)
- [x] `app/core/dependencies/ocr.py` — `get_ocr_job_service` (단일 db 세션 공유)
- [x] `POST /ocr/jobs` 등록됨 (응답은 임시 `{"message": "test"}`)
- [ ] `POST /ocr/jobs` 응답을 `202 + {job_id, status}`로 교체
- [ ] `GET /ocr/jobs/{id}` 본문 구현 (현재 `pass`)
- [x] `entrypoint.sh`의 워커 큐 이름 `-Q ocr`

### Phase 5 — 검증 (TODO)
- [ ] `POST /ocr/jobs` → `202 {job_id}` 응답 확인
- [ ] Flower(`http://localhost:5555`)에서 STARTED → SUCCESS 흐름 관찰
- [ ] `GET /ocr/jobs/{job_id}` → status 변화 (pending → started → success)
- [ ] 의도적으로 잘못된 파일 보내 `failed` 케이스 확인
- [ ] (선택) Cleanup 잡 — 7일 지난 임시 파일/실패 잡 삭제

---

## 8. 운영 시 고려사항

### 8-1. 임시 파일 청소
`save_file`로 저장된 파일은 작업 후 삭제해야 디스크가 차지 않음. 옵션:
- 워커에서 OCR 후 즉시 `unlink` (단, 재시도 시 파일 없음 → 멱등성 깨짐)
- 별도 cleanup 태스크가 24시간 후 일괄 삭제 (권장)

### 8-2. 재시도 정책
일시적 실패(예: Clova API 5xx/429, 네트워크 타임아웃)는 재시도가 의미 있지만, 잘못된 이미지는 재시도해도 실패. 태스크에 명시적 retry:

```python
import httpx

@celery.task(
    bind=True,
    autoretry_for=(httpx.TimeoutException, httpx.ConnectError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def run_ocr(self, job_id: str): ...
```

EasyOCR/PaddleOCR(로컬 추론)은 재시도해도 같은 에러가 또 날 가능성이 높아 의미가 적음. **Clova API 의존 잡에만 적용 권장.**

### 8-3. 클라이언트 폴링 대신 푸시
폴링은 단순하지만 비효율적. 대안:
- **Server-Sent Events (SSE)**: HTTP 그대로 + 단방향 푸시
- **WebSocket**: `/ws/jobs/{id}` 구독 → 워커가 완료 시 publish
- **Webhook**: 작업 등록 시 `callback_url` 받아서 워커가 POST

처음에는 폴링으로 시작 → 트래픽 늘어나면 SSE/WebSocket.

### 8-4. job_id 보안 (멀티테넌시)
다른 사용자가 남의 job_id를 조회하지 못하도록 토큰의 `sub`/`user_id`와 매칭:

```python
# 모델에 user_id 추가
class OcrJob(Base):
    ...
    user_id = Column(String(50), nullable=False, index=True)

# 조회 시
if ocr_job.user_id != current_user.id:
    raise BusinessException(code=403, message="forbidden")
```

### 8-5. 결과 크기
OCR 결과(텍스트 박스, 좌표, confidence)가 클 수 있음. 작은 건 `JSON` 컬럼 OK, 큰 건 별도 파일 스토리지(S3/로컬)로 빼고 `result_url`만 저장.

---

## 9. 빠른 참조 — API 스펙

### 잡 생성 (현재 임시 응답)
```http
POST /api/v1/ocr/jobs HTTP/1.1
Authorization: Bearer <token>
Content-Type: multipart/form-data

file=<image>&engine=easyocr
```

현재 응답:
```json
{ "message": "test" }
```

권장 응답:
```http
202 Accepted
{
  "job_id": "5b8e0a64-...",
  "status": "pending"
}
```

### 상태 조회 (TODO)
```http
GET /api/v1/ocr/jobs/5b8e0a64-... HTTP/1.1
Authorization: Bearer <token>
```

권장 응답:
```json
{
  "job_id": "5b8e0a64-...",
  "status": "success",
  "engine": "easyocr",
  "file_name": "receipt.jpg",
  "result": { "images": [{ "text": "...", "boundingPoly": [...], "confidence": 0.97 }] },
  "info": null,
  "created_at": "2026-04-29T16:30:00",
  "started_at": "2026-04-29T16:30:01",
  "finished_at": "2026-04-29T16:30:08"
}
```

상태 값: `pending` · `started` · `success` · `failed`

---

## 10. 남은 TODO

| 항목 | 위치 | 비고 |
|---|---|---|
| **실제 OCR 추론 호출** | `app/worker/tasks/ocr.py:21-22` | `OcrModule(engine).engine.recognize(Path(file_path))` 연결 |
| **`POST /ocr/jobs` 응답 교체** | `app/api/v1/ocr/router.py:33-40` | `{"message": "test"}` → `202 + {job_id, status}` |
| **`GET /ocr/jobs/{id}` 구현** | `app/api/v1/ocr/router.py:43-45` | DB에서 `OcrJob` 조회 후 status/result 반환 |
| **잡 응답 스키마 추가** | `app/schemas/ocr/job.py` (신규) | `OcrJobCreated`, `OcrJobResult` |
| **Repository 메서드 확장** | `app/repositories/ocr.py` | `get(job_id)` — async 조회용 |
| **임시 파일 cleanup 태스크** | `app/worker/tasks/cleanup.py` (신규) | 24h 경과 파일 삭제 |
| **잡 소유권 검증** | `OcrJob` 모델 + 조회 라우터 | `user_id` 컬럼 추가 |

> `info` 컬럼에 `e.__traceback__` 객체를 그대로 넣으면 JSON 직렬화 실패. `traceback.format_exc()` 등 문자열로 변환해야 함 (`app/worker/tasks/ocr.py:25` 참고).
