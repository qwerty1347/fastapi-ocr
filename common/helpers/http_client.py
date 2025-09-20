import httpx

from typing import Any


async def http_get(
    url: str,
    params: dict[str, object] | None = None,
    headers: dict[str, object] | None = None,
    timeout: int = 10
) -> httpx.Response | None:
    async with httpx.AsyncClient(timeout=timeout) as client:
        """
        HTTP GET 요청을 수행하는 비동기 함수

        매개변수:
        - url (str): 요청할 URL
        - params (dict[str, object] | None): 요청 쿼리 매개변수 (기본값: None)
        - headers (dict[str, object] | None): 요청 헤더 (기본값: None)
        - timeout (int): 타임아웃 시간 (기본값: 10초)

        반환값:
        - httpx.Response | None: 요청에 대한 응답 객체, 요청 실패 시 None
        """
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response


async def http_post(
    url: str,
    *,
    data: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 10
) -> httpx.Response:
    """
    HTTP POST 요청을 수행하는 비동기 함수

    매개변수:
    - url (str): 요청할 URL
    - data (dict[str, Any]): 전송할 데이터 (기본값: None)
    - json (dict[str, Any]): 전송할 JSON 데이터 (기본값: None)
    - files (dict[str, tuple[str, bytes, str]] | None): 업로드할 파일들 (기본값: None)
    - headers (dict[str, str]): 요청 헤더 (기본값: None)
    - timeout (int): 타임아웃 시간 (기본값: 10초)

    반환값:
    - httpx.Response: 요청의 응답 객체
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, data=data, json=json, files=files, headers=headers)
        response.raise_for_status()
        return response.json()