"""delete_task — Open API 삭제 불가(404) 시 [중복] + 완료 처리 폴백 검증"""

import os
from unittest import mock

import pytest

os.environ.setdefault("DOORAY_API_TOKEN", "test-token")
os.environ.setdefault("DOORAY_TENANT_ID", "123")

from src.client import DoorayClient  # noqa: E402
from src.validators import ValidationError  # noqa: E402

TASK = {
    "id": "111",
    "subject": "[거래처 신규 등록] 테스트",
    "body": {"mimeType": "text/x-markdown", "content": "본문"},
    "users": {
        "from": {"type": "member", "member": {"organizationMemberId": "9"}},
        "to": [{"type": "member", "member": {"organizationMemberId": "1", "name": "A"},
                "workflow": {"id": "w"}}],
        "cc": [{"type": "member", "member": {"organizationMemberId": "2", "name": "B"}}],
    },
    "tags": [{"id": "t1"}],
    "milestone": None,
    "dueDate": None,
    "priority": "none",
    "workflowClass": "registered",
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DOORAY_WEB_URL", "https://example.dooray.com")
    c = DoorayClient()
    monkeypatch.setattr(c, "get_task", lambda post_id, pid=None: dict(TASK))
    return c


def test_delete_success(client):
    with mock.patch.object(client, "_delete") as d, mock.patch.object(client, "_put") as p:
        r = client.delete_task("111", "222")
    d.assert_called_once()
    p.assert_not_called()
    assert r["삭제된_태스크"] == TASK["subject"]


def test_delete_404_falls_back_to_mark(client):
    with mock.patch.object(client, "_delete", side_effect=ValidationError("[x] HTTP 404: {}")), \
         mock.patch.object(client, "_put") as p, mock.patch.object(client, "api") as a:
        r = client.delete_task("111", "222")
    assert r["deleted"] is False
    payload = p.call_args[0][1]
    assert payload["subject"] == "[중복] [거래처 신규 등록] 테스트"
    # 전체 교체 PUT 이므로 기존 필드를 보존해야 한다
    assert payload["body"] == {"mimeType": "text/x-markdown", "content": "본문"}
    assert payload["users"]["to"] == [{"type": "member", "member": {"organizationMemberId": "1"}}]
    assert payload["users"]["cc"] == [{"type": "member", "member": {"organizationMemberId": "2"}}]
    assert payload["tagIds"] == ["t1"]
    assert a.call_args[0][1].endswith("/posts/111/set-done")
    assert r["web_link"] == "https://example.dooray.com/task/222/111"


def test_mark_is_idempotent(client, monkeypatch):
    done = dict(TASK, subject="[중복] x", workflowClass="closed")
    monkeypatch.setattr(client, "get_task", lambda post_id, pid=None: done)
    with mock.patch.object(client, "_delete", side_effect=ValidationError("HTTP 404")), \
         mock.patch.object(client, "_put") as p, mock.patch.object(client, "api") as a:
        r = client.delete_task("111", "222")
    p.assert_not_called()
    a.assert_not_called()
    assert r["변경사항"] == []


def test_other_errors_propagate(client):
    with mock.patch.object(client, "_delete", side_effect=ValidationError("HTTP 403: denied")):
        with pytest.raises(ValidationError):
            client.delete_task("111", "222")
