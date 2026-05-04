# 워커에서 OCR을 동기로 실행하기

## 배경

현재 OCR 엔진은 모두 **async**로 작성돼 있고, FastAPI의 `POST /ocr/`(동기 응답) 경로에서 `await`로 호출됩니다.

```
app/services/ocr/ocr.py        OcrService.do_ocr          (async)
  └─ app/services/ocr/module.py  OcrModule.recognize        (async)
       └─ app/module/ocr/{easyocr,paddleocr,clovaocr}.py     async def recognize(file: UploadFile)
```

반면 Celery 워커 태스크 `app/worker/tasks/ocr.py`의 `run_ocr`은 **sync** 컨텍스트(`with sync_session_factory()`)에서 돕니다. 여기서 OCR 추론을 실행해야 하는데, 엔진이 async라 그대로는 못 부릅니다.

이 문서는 **워커에서 OCR을 sync로 호출하는 구조**를 설계합니다.

---

## 1. 왜 워커는 sync여야 하는가

Celery 워커는 기본적으로 sync 컨텍스트입니다. async 코드를 끌어쓰려면:

- 매 태스크마다 새 이벤트 루프를 띄우거나(`asyncio.run`),
- async 풀(`celery[gevent]`, `celery[eventlet]`)을 별도로 운영하거나,
- `celery_pool_asyncio` 같은 비공식 풀을 써야 합니다.

OCR은 **CPU 바운드**(EasyOCR/PaddleOCR 로컬 추론)이거나 **단일 외부 HTTP 콜**(Clova) 한 번이라 async로 얻는 동시성 이득이 없습니다. 워커에서는 다음이 더 자연스럽습니다.

- 워커 1 프로세스 = 1 잡 동시 실행 (`worker_prefetch_multiplier=1`, prefork 풀)
- 추론은 sync 함수로 직진
- DB 세션도 이미 `sync_session_factory` 사용 중

따라서 **엔진의 추론 코어를 sync 함수로 노출**하고, FastAPI가 이를 async로 감싸는 구조가 깔끔합니다.

---

## 2. 선택지

| 옵션 | 워커에서 쓰는 방법 | 장점 | 단점 |
|---|---|---|---|
| **A. `asyncio.run()` 으로 감싸기** | `asyncio.run(engine.recognize(...))` | 코드 변경 최소 | 워커에서 매 잡마다 루프 생성/파괴, ClovaOcr만 의미 있는데 그 외 엔진은 헛수고 |
| **B. sync 코어 + async 어댑터 (권장)** | 엔진에 `recognize_path(path) -> dict` (sync) 추가, async `recognize(file)`는 sync 코어를 호출하는 얇은 wrapper | API/워커가 같은 코어 공유, EasyOCR·PaddleOCR이 원래 sync 라이브러리라 자연스러움 | 엔진 클래스 시그니처 변경 |
| **C. 엔진을 완전히 sync로 되돌림** | API에서 `await asyncio.to_thread(engine.recognize_path, path)` | 가장 단순한 코어 | API 라우트 시그니처/테스트가 같이 흔들림 |

**옵션 B**가 변경 폭과 일관성 측면에서 가장 좋습니다. 아래는 옵션 B 기준 설계.

> 옵션 A는 "지금 당장 굴러가게만" 할 때만 쓰세요. 매 태스크마다 `asyncio.run`은 새 루프를 만듭니다 — `httpx.AsyncClient` 커넥션 풀이 잡 단위로 버려지는 등 리소스 비효율이 누적됩니다.

---

## 3. 엔진 인터페이스 재설계

### 3-1. `BaseEngine` — sync 메서드를 1급 시민으로

```python
# app/module/ocr/base.py
from abc import ABC, abstractmethod
from pathlib import Path

from fastapi import UploadFile


class BaseEngine(ABC):
    @abstractmethod
    def recognize_path(self, file_path: Path) -> dict:
        """디스크에 이미 저장된 이미지를 sync로 OCR. 워커/배치 진입점."""

    async def recognize(self, file: UploadFile) -> dict:
        """API용 어댑터. UploadFile을 디스크에 저장 후 sync 코어 호출."""
        from app.core.utils.file import delete_file, save_file
        file_path = await save_file(file)
        try:
            return await asyncio.to_thread(self.recognize_path, file_path)
        finally:
            await delete_file(file_path)

    @abstractmethod
    def convert_to_json(self, ocr_result) -> dict: ...
```

> `recognize`(API)는 `await asyncio.to_thread(...)`로 sync 코어를 워커 스레드에서 돌립니다 → 이벤트 루프를 막지 않음. 현재 코드는 `self.ocr.readtext()`를 `await` 없이 직접 호출해 사실상 루프를 블로킹하는 잠재 버그가 있는데, 이 리팩터로 같이 해소됩니다.

### 3-2. EasyOCR

```python
# app/module/ocr/easyocr.py
from pathlib import Path

import easyocr

from app.module.ocr.base import BaseEngine


class EasyOcr(BaseEngine):
    def __init__(self):
        self.ocr = easyocr.Reader(['ko', 'en'])

    def recognize_path(self, file_path: Path) -> dict:
        response = self.ocr.readtext(str(file_path))
        return self.convert_to_json(response)

    def convert_to_json(self, response):
        result = {"images": []}
        for poly, text, confidence in response:
            bounding_poly = [[int(v[0]), int(v[1])] for v in poly]
            result["images"].append({
                "boundingPoly": bounding_poly,
                "text": text,
                "confidence": float(confidence),
            })
        return result
```

### 3-3. PaddleOCR

```python
# app/module/ocr/paddleocr.py
from pathlib import Path

from paddleocr import PaddleOCR

from app.module.ocr.base import BaseEngine


class PaddleOcr(BaseEngine):
    def __init__(self):
        self.ocr = PaddleOCR(lang='korean')

    def recognize_path(self, file_path: Path) -> dict:
        response = self.ocr.ocr(str(file_path))
        return self.convert_to_json(response)

    def convert_to_json(self, response):
        result = {"images": []}
        for line in response[0]:
            result["images"].append({
                "boundingPoly": line[0],
                "text": line[1][0],
                "confidence": float(line[1][1]),
            })
        return result
```

### 3-4. ClovaOCR — sync HTTP

`httpx.AsyncClient` 대신 `httpx.Client`를 씁니다. 워커에서 호출되는 sync 경로이므로 그 편이 자연스럽고, FastAPI 경로도 `asyncio.to_thread`로 들어오기 때문에 sync HTTP가 문제되지 않습니다.

```python
# app/module/ocr/clovaocr.py
import json
import time
import uuid
from pathlib import Path

import httpx

from app.core.config import config
from app.core.utils.file import get_file_extension
from app.module.ocr.base import BaseEngine


class ClovaOcr(BaseEngine):
    def recognize_path(self, file_path: Path) -> dict:
        post_url, files, headers = self._build_form_data(file_path)
        with httpx.Client(timeout=30) as client:
            response = client.post(post_url, files=files, headers=headers)
            response.raise_for_status()
            ocr_result = response.json()
        return self.parse_inferText(ocr_result)

    def _build_form_data(self, file_path: Path):
        ext = get_file_extension(file_path.name)
        message = {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "lang": "ko",
            "images": [{"format": ext, "name": file_path.name}],
        }
        files = {
            "file": (file_path.name, file_path.read_bytes(), f"image/{ext}"),
            "message": (None, json.dumps(message), "application/json"),
        }
        headers = {"X-OCR-SECRET": config.CLOVA_OCR_SECRET_KEY}
        return config.CLOVA_OCR_APIGW_INVOKE_URL, files, headers

    def parse_inferText(self, ocr_result) -> dict:
        infer_texts = []
        for image in ocr_result.get("images", []):
            for field in image.get("fields", []):
                t = field.get("inferText")
                if t:
                    infer_texts.append(t)
        ocr_result["full_text"] = " ".join(infer_texts)
        return ocr_result

    def convert_to_json(self, ocr_result) -> dict:
        return ocr_result
```

> 기존 `build_form_data`는 `UploadFile.read()` 기반(async). 워커는 디스크에 저장된 파일만 보므로 `Path.read_bytes()` 기반 sync 빌더가 자연스럽습니다.

### 3-5. `OcrModule` — sync 진입점도 노출

```python
# app/services/ocr/module.py
from pathlib import Path

from fastapi import UploadFile

from app.module.ocr.clovaocr import ClovaOcr
from app.module.ocr.easyocr import EasyOcr
from app.module.ocr.paddleocr import PaddleOcr


class OcrModule:
    OCR_ENGINES = {
        "easyocr": EasyOcr(),
        "paddleocr": PaddleOcr(),
        "clovaocr": ClovaOcr(),
    }

    def __init__(self, engine: str):
        self.engine = self.OCR_ENGINES[engine]

    async def recognize(self, file: UploadFile) -> dict:
        return await self.engine.recognize(file)

    def recognize_path(self, file_path: Path) -> dict:
        return self.engine.recognize_path(file_path)
```

---

## 4. Celery 태스크 — sync 경로

`app/worker/tasks/ocr.py`의 TODO 부분을 채웁니다.

```python
# app/worker/tasks/ocr.py
import traceback
from pathlib import Path

from sqlalchemy import func

from app.infrastructure.database.session import sync_session_factory
from app.models.ocr_job import JobStatus, OcrJob
from app.services.ocr.module import OcrModule
from app.worker.celery_app import celery


@celery.task
def run_ocr(job_id: str):
    with sync_session_factory() as session:
        ocr_job = session.get(OcrJob, job_id)
        if ocr_job is None:
            return

        ocr_job.status = JobStatus.STARTED
        ocr_job.started_at = func.now()
        session.commit()

        try:
            result = OcrModule(ocr_job.engine).recognize_path(Path(ocr_job.file_path))
        except Exception as e:
            ocr_job.status = JobStatus.FAILED
            ocr_job.info = {
                "error": e.__class__.__name__,
                "message": str(e),
                "traceback": traceback.format_exc(),
            }
            ocr_job.finished_at = func.now()
            session.commit()
            raise
        else:
            ocr_job.status = JobStatus.SUCCESS
            ocr_job.result = result
            ocr_job.finished_at = func.now()
            session.commit()
```

### 변경 포인트

1. **`recognize_path`로 sync 호출** — 이벤트 루프 없음, `await`/`asyncio.run` 없음.
2. **`UploadFile` 의존 제거** — 워커는 `ocr_job.file_path`(이미 디스크 위)만 봄. API가 저장하고, 워커가 읽고, **워커가 다 쓴 뒤 삭제**(아래 5-2 참고).
3. **`info`의 traceback** — `e.__traceback__`은 객체라 JSON 직렬화 실패. `traceback.format_exc()`로 문자열화 (이건 문서 01의 마지막 노트와 동일).
4. **`raise` 재전파** — Celery에 FAILED를 인식시키기 위함. (문서 01 §4-2 핵심원칙 4번)

---

## 5. 파일 수명 주기 정리

기존 동기 API(`POST /ocr/`)는 엔진 내부에서 `save_file → recognize → delete_file`이 한 번에 처리됐습니다. 비동기 잡 흐름에서는 두 단계로 갈라집니다.

```
API: save_file(UploadFile) → DB INSERT(file_path) → enqueue
                                                       │
                                                       ▼
Worker: read file_path → recognize_path → delete_file (또는 cleanup task)
```

### 5-1. 엔진 내부에서는 더 이상 파일을 저장/삭제하지 않음

- 새 `recognize_path(file_path)`는 파일을 **읽기만** 함.
- 파일 라이프사이클은 호출 측 책임.
  - API 직접 호출 시(`/ocr/`): `BaseEngine.recognize`의 `try/finally`가 정리 (3-1 참고).
  - 워커 잡: 워커 또는 cleanup 태스크가 정리 (5-2).

### 5-2. 워커에서의 파일 정리

옵션 1 — 워커가 잡 끝에 즉시 삭제:

```python
finally:
    Path(ocr_job.file_path).unlink(missing_ok=True)
```

장점: 디스크가 즉시 비워짐.
단점: `task_acks_late=True` + 재시도 시 파일 없음 → 멱등성 깨짐. 디버깅 시 원본도 사라짐.

옵션 2 (권장) — **별도 cleanup 태스크**가 24h 경과 파일을 일괄 삭제. 문서 01 §8-1과 같은 정책. 디버깅 여지를 남기면서 디스크 사용량도 통제 가능.

---

## 6. API 경로(`POST /ocr/`)는 그대로 동작하는가

네. 변경된 흐름:

```
POST /ocr/  →  OcrService.do_ocr (async)
              └─ OcrModule.recognize (async)
                  └─ BaseEngine.recognize (async wrapper)
                      ├─ await save_file(UploadFile)
                      ├─ await asyncio.to_thread(self.recognize_path, path)   ← sync 코어
                      └─ await delete_file(path)
```

기존과 외부 동작은 동일. 차이점:

- 추론이 워커 스레드에서 돌아 **이벤트 루프가 풀린다** (현재는 `self.ocr.readtext`가 sync인데 `await` 없이 직접 호출돼 루프를 블로킹).
- `ClovaOcr`은 `httpx.Client`(sync) + `to_thread` 조합으로 바뀜. 단일 외부 콜이라 동시성 손해 거의 없음.

---

## 7. 마이그레이션 체크리스트

### 코드 변경

- [ ] `app/module/ocr/base.py` — `recognize_path(file_path: Path)` abstractmethod 추가, async `recognize`는 wrapper로
- [ ] `app/module/ocr/easyocr.py` — `recognize_path` 구현, 기존 async `recognize` 제거(베이스가 처리)
- [ ] `app/module/ocr/paddleocr.py` — 동일
- [ ] `app/module/ocr/clovaocr.py` — `recognize_path` + `_build_form_data(Path)` + `httpx.Client` 전환
- [ ] `app/services/ocr/module.py` — `recognize_path(path)` 추가
- [ ] `app/worker/tasks/ocr.py` — `OcrModule(engine).recognize_path(Path(file_path))` 호출 + `traceback.format_exc()` + `raise`

### 검증

- [ ] `POST /ocr/` 동기 엔드포인트 — 기존과 동일하게 응답 (각 엔진별)
- [ ] `POST /ocr/jobs` → `GET /ocr/jobs/{id}` — `pending → started → success` 전이
- [ ] 잘못된 이미지(예: 0바이트) 업로드 → `failed` + `info.traceback` 채워지는지
- [ ] Flower(`http://localhost:5555`) 태스크 상태 = SUCCESS/FAILURE 와 DB `ocr_jobs.status` 일치
- [ ] 동기 API로 추론 중에 다른 요청을 보낼 때 응답이 막히지 않는지 (이벤트 루프 비블로킹 확인)

---

## 8. 자주 묻는 함정

### Q1. 그냥 `asyncio.run(engine.recognize(file))` 안 되나?

워커 태스크 안에서 동작은 합니다. 그러나:

- `UploadFile`을 워커가 만들 수 없음 → 어차피 인터페이스 변경 필요.
- 매 잡마다 새 이벤트 루프 + `httpx.AsyncClient` 풀 폐기 → 자원 낭비.
- ClovaOcr 외 엔진은 내부가 sync인데 굳이 async 래퍼를 거쳐 풀어내는 비대칭.

### Q2. `nest_asyncio`로 기존 async를 덮어쓰면 안 되나?

`nest_asyncio`는 이미 돌고 있는 루프 위에 또 루프를 박는 패치라 디버깅 난이도만 올라갑니다. 워커는 sync 컨텍스트라 그런 패치도 필요 없습니다. 사용하지 마세요.

### Q3. EasyOCR/PaddleOCR 모델 객체를 워커 프로세스 간에 공유할 수 있나?

`OCR_ENGINES`는 클래스 변수로 import 시점에 한 번 인스턴스화. **prefork 풀**이면 워커 프로세스 자식마다 별도 메모리(메인 프로세스가 fork되며 모델이 복제됨). gevent/eventlet에서는 공유 가능하지만 GPU 추론은 prefork가 안전합니다. `worker_max_tasks_per_child=200`이 모델의 잠재적 메모리 누수를 막아주므로 그대로 두세요 (문서 01 §4-1).

### Q4. `recognize`(async)와 `recognize_path`(sync), 두 개 유지 vs `recognize_path`만 노출

API 라우터/서비스가 `UploadFile`을 직접 받기 때문에 **양쪽 모두 유지**가 편합니다. 그렇지 않으면 라우터에서 매번 `save_file → to_thread → delete_file`을 반복해야 함. base의 wrapper가 그 책임을 흡수하도록 둡니다.

---

## 9. 한 줄 요약

> 엔진의 핵심 추론을 **sync `recognize_path(Path) -> dict`**로 정의하고, async `recognize(UploadFile)`는 그 위의 얇은 wrapper로 둔다. 워커 태스크는 sync 경로를 직접 호출하고, FastAPI는 `asyncio.to_thread`로 호출한다.
