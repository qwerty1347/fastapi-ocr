FROM python:3.11
## paddleocr 호환

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN pip install --upgrade pip setuptools wheel
RUN pip install uv

# pyproject.toml(원하는 의존성 명세)과 uv.lock(실제 설치된 정확한 버전·해시)을 함께 복사한다.
# 두 파일이 모두 있어야 uv가 lock에 박제된 버전으로 재현성 있게 설치할 수 있다.
# 앱 코드(./app)보다 먼저 복사하므로 코드만 바뀐 빌드에서는 의존성 설치 레이어가 캐시되어 빠르다.
COPY pyproject.toml uv.lock ./

# --no-dev: pytest 등 dev 의존성은 제외 (운영 이미지 슬림화)
# --frozen: lock과 pyproject가 어긋나면 빌드를 실패시킨다. uv가 조용히 lock을 갱신해
#           "어제는 됐는데 오늘 안 됨" 사고를 막고, CI/Docker 빌드의 재현성을 강제한다.
RUN uv sync --no-dev --frozen

COPY ./app /app
COPY .env .env
COPY .docker/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]