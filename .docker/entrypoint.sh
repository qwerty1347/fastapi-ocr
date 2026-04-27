#!/bin/sh
set -e

# SERVICE_TYPE 환경변수로 서비스 역할 분기
# docker-compose.yml의 각 서비스에서 environment로 지정
case "$SERVICE_TYPE" in
    app)
        uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
        exec uv run jupyter notebook --ip=0.0.0.0 --port=8888 --allow-root --no-browser --notebook-dir=/app/notebooks
        ;;
    worker)
        # 여러 큐 처리 가능하도록 수정
        exec uv run celery -A app.worker.celery_app worker \
            --loglevel=info \
            -Q default \
            --concurrency=2
        ;;
    flower)
        # Celery Flower 모니터링 UI
        exec uv run celery -A app.worker.celery_app flower --port=5555
        ;;
    *)
        echo "ERROR: SERVICE_TYPE is not set or invalid: '$SERVICE_TYPE'"
        echo "Valid values: app | worker | flower"
        exit 1
        ;;
esac