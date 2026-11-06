"""파일 업로드 307 리다이렉트 처리·위키 본문 치환 테스트 (네트워크 없이 mock)"""

import json
import os
from unittest import mock

import pytest

os.environ.setdefault("DOORAY_API_TOKEN", "test-token")
os.environ.setdefault("DOORAY_TENANT_ID", "123")

from src.client import DoorayClient  # noqa: E402
from src.validators import ValidationError  # noqa: E402


def _resp(status, headers=None, body=None):
    r = mock.Mock()
    r.status_code = status
    r.headers = headers or {}
    data = body if body is not None else {"header": {"isSuccessful": True}, "result": {"id": "f1"}}
    r.content = json.dumps(data).encode()
    r.json.return_value = data
    r.text = json.dumps(data)
    return r


@pytest.fixture
def client():
    return DoorayClient()


@pytest.fixture
def tmpfile(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("hello")
    return str(p)


def test_upload_follows_307_with_auth(client, tmpfile):
    loc = "https://file-api.dooray.com/uploads/wiki/v1/wikis/1/files"
    with mock.patch("src.client.requests.request",
                    side_effect=[_resp(307, {"location": loc}), _resp(200)]) as req:
        result = client.api_upload("/wiki/v1/wikis/1/files", tmpfile)
    assert result == {"id": "f1"}
    assert req.call_count == 2
    first, second = req.call_args_list
    assert first.kwargs["allow_redirects"] is False
    assert second.args[1] == loc
    assert second.kwargs["headers"]["Authorization"].startswith("dooray-api ")
    assert "file" in second.kwargs["files"]


def test_upload_refuses_non_dooray_redirect(client, tmpfile):
    with mock.patch("src.client.requests.request",
                    return_value=_resp(307, {"location": "https://evil.example.com/x"})):
        with pytest.raises(ValidationError):
            client.api_upload("/wiki/v1/wikis/1/files", tmpfile)


def test_is_dooray_host():
    assert DoorayClient._is_dooray_host("https://file-api.dooray.com/x")
    assert not DoorayClient._is_dooray_host("http://file-api.dooray.com/x")
    assert not DoorayClient._is_dooray_host("https://dooray.com.evil.com/x")


def test_drive_update_content_uses_redirect(tmpfile):
    from src import server as srv
    import asyncio

    loc = "https://file-api.dooray.com/drive/v1/drives/d/files/f"
    with mock.patch("src.client.requests.request",
                    side_effect=[_resp(307, {"location": loc}), _resp(200)]) as req:
        out = asyncio.run(srv.mcp.call_tool(
            "dooray_drive_update_file_content",
            {"drive_id": "d", "file_id": "f", "file_path": tmpfile},
        ))
    if isinstance(out, tuple):
        out = out[0]
    assert "교체 완료" in out[0].text
    assert req.call_args_list[0].args[0] == "PUT"
    assert req.call_args_list[1].args[1] == loc


def _call(name, args):
    from src import server as srv
    import asyncio

    out = asyncio.run(srv.mcp.call_tool(name, args))
    if isinstance(out, tuple):
        out = out[0]
    return out[0].text


def test_wiki_replace_text_ok():
    page = {"body": {"mimeType": "text/x-markdown", "content": "링크: old-url 끝"}}
    with mock.patch("src.client.DoorayClient.api", side_effect=[page, None]) as api:
        text = _call("dooray_wiki_page_replace_text", {
            "wiki_id": "w", "page_id": "p",
            "replacements_json": json.dumps([{"find": "old-url", "replace": "new-url"}]),
        })
    assert "치환 완료" in text
    put = api.call_args_list[1]
    assert put.kwargs["payload"]["body"]["content"] == "링크: new-url 끝"


def test_wiki_replace_text_refuses_ambiguous():
    page = {"body": {"mimeType": "text/x-markdown", "content": "a a"}}
    with mock.patch("src.client.DoorayClient.api", side_effect=[page]) as api:
        text = _call("dooray_wiki_page_replace_text", {
            "wiki_id": "w", "page_id": "p",
            "replacements_json": json.dumps([{"find": "a", "replace": "b"}]),
        })
    assert "저장하지 않았습니다" in text
    assert api.call_count == 1
