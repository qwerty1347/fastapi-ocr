from celery import Celery

from app.core.config import config


celery = Celery(
    "fastapi_ocr",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
)

# 큐 정의:
#   - ocr     : 이미지 OCR 태스크 (heavy, GPU/CPU 점유)
#   - default : 가벼운 잡태스크 (예: add_number, 이메일 발송 등)
# entrypoint.sh의 워커 -Q 인자는 "ocr,default"로 맞춰 두 큐 모두 처리하게 한다.
celery.conf.task_queues = {
    "ocr": {},
    "default": {},
}
celery.conf.task_default_queue = "ocr"

celery.conf.update(
    # 워커가 한 번에 미리 가져올 태스크 수. 기본 4 → 무거운 OCR 추론은 한 워커가 선점해
    # 다른 워커가 놀게 되므로 1로 두어 작업이 사용 가능한 워커에 골고루 분배되게 한다.
    worker_prefetch_multiplier=1,

    # 태스크가 끝난 뒤에 ack를 보낸다. 워커가 도중에 죽으면 broker가 같은 태스크를
    # 다른 워커에 재할당해 유실을 막는다. OCR은 ocr_jobs 테이블의 job_id를 키로
    # 같은 row를 갱신만 하므로(SELECT → UPDATE status/result) 재실행되어도 중복 사이드이펙트가
    # 없어 멱등하다. 따라서 acks_late를 켜는 것이 안전하다.
    task_acks_late=True,

    # 워커 프로세스가 비정상 종료(SIGKILL/OOM 등)되면 태스크를 명시적으로 reject 하여
    # broker가 재큐하게 만든다. task_acks_late와 짝으로 쓰며 같은 멱등성 전제를 따른다.
    task_reject_on_worker_lost=True,

    # 태스크 hard time limit (초). 초과 시 워커가 강제 종료. OCR 한 장은 보통 5~30초이므로
    # 5분이면 충분히 여유가 있는 한계값. 멈춘 작업이 워커를 영구 점유하는 사고를 방지한다.
    task_time_limit=60 * 5,

    # soft time limit (초). 초과 시 태스크 안에서 SoftTimeLimitExceeded 예외가 발생해
    # 임시 파일 정리 등 cleanup 코드를 실행할 기회를 준다. hard limit보다 약간 짧게 잡는다.
    task_soft_time_limit=60 * 4,

    # 결과 backend(Redis DB 1)에 저장된 Celery 메타 결과의 만료 시간(초).
    # 실제 OCR 결과는 ocr_jobs 테이블에 저장되므로 Celery 결과는 짧게 유지해도 무방.
    result_expires=60 * 60 * 24,

    # 워커가 태스크를 시작하면 STARTED 상태로 표시. Flower나 AsyncResult에서
    # PENDING(대기중) ↔ STARTED(실행중) 구분이 가능해져 모니터링/디버깅에 유리.
    # ocr_jobs 테이블의 status 컬럼과 별개로 Celery 측에서도 추적 가능하게 한다.
    task_track_started=True,

    # 직렬화 포맷. 보안상 pickle은 피하고 json으로 통일.
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # 시간대. 로그/스케줄에 한국 시간이 찍히도록 한다.
    timezone="Asia/Seoul",
    enable_utc=False,

    # 워커가 일정 횟수 태스크를 처리한 뒤 자식 프로세스를 재시작하여 메모리 누수를 방지한다.
    # PaddleOCR/EasyOCR은 모델을 메모리에 들고 있어 장시간 누수 가능성이 있다.
    worker_max_tasks_per_child=200,
)


import app.worker.tasks  # noqa: F401, E402