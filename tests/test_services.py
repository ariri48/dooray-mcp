"""서비스 API 툴 레이어 테스트 — 등록/요청 경로/confirm 가드 검증"""

import asyncio
import json
import os
from unittest import mock

import pytest

os.environ.setdefault("DOORAY_API_TOKEN", "test-token")
os.environ.setdefault("DOORAY_TENANT_ID", "123")


def _fake_response(result=None, total=0):
    resp = mock.Mock()
    resp.status_code = 200
    body = {"header": {"isSuccessful": True}, "result": result, "totalCount": total}
    resp.content = json.dumps(body).encode()
    resp.json.return_value = body
    return resp


@pytest.fixture(scope="module")
def server():
    from src import server as srv
    return srv


def _call_tool(server, name, args):
    result = asyncio.run(server.mcp.call_tool(name, args))
    # FastMCP은 (content_list, raw_result) 튜플 또는 content_list 형태로 반환
    if isinstance(result, tuple):
        result = result[0]
    return json.loads(result[0].text)


def test_all_services_registered(server):
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    # 서비스별 대표 툴 존재 확인
    expected = {
        "dooray_common_me",
        "dooray_common_list_streams",
        "dooray_project_create",
        "dooray_workflow_create",
        "dooray_milestone_update",
        "dooray_template_create",
        "dooray_post_set_workflow",
        "dooray_post_set_done",
        "dooray_calendar_create_event",
        "dooray_calendar_list_events",
        "dooray_drive_list",
        "dooray_drive_shared_link_create",
        "dooray_wiki_page_create",
        "dooray_wiki_comment_create",
        "dooray_messenger_direct_send",
        "dooray_messenger_channel_create",
        "dooray_resource_categories",
        "dooray_reservation_create",
        "dooray_contacts_search",
        "dooray_api_call",
    }
    missing = expected - names
    assert not missing, f"미등록 툴: {missing}"
    assert len(names) == len(tools), "중복 툴 이름 존재"


def test_calendar_list_events_request_path(server):
    with mock.patch("requests.request", return_value=_fake_response([], 0)) as m:
        data = _call_tool(server, "dooray_calendar_list_events", {
            "time_min": "2026-07-01T00:00:00+09:00",
            "time_max": "2026-07-31T23:59:59+09:00",
        })
    assert data["events"] == []
    method, url = m.call_args[0][0], m.call_args[0][1]
    assert method == "GET"
    assert url == "https://api.dooray.com/calendar/v1/calendars/*/events"
    params = m.call_args[1]["params"]
    assert params["timeMin"] == "2026-07-01T00:00:00+09:00"


def test_messenger_direct_send_payload(server):
    with mock.patch("requests.request", return_value=_fake_response()) as m:
        data = _call_tool(server, "dooray_messenger_direct_send", {
            "organization_member_id": "999",
            "text": "안녕하세요",
        })
    assert "발송 완료" in data["message"]
    payload = m.call_args[1]["json"]
    assert payload == {"organizationMemberId": "999", "text": "안녕하세요"}


def test_delete_requires_confirm(server):
    # confirm=False면 실제 API 호출 없이 확인 요청만 반환
    with mock.patch("requests.request") as m:
        data = _call_tool(server, "dooray_wiki_page_delete", {
            "wiki_id": "1", "page_id": "2",
        })
    assert data.get("confirm_required") is True
    m.assert_not_called()


def test_api_call_generic(server):
    with mock.patch("requests.request", return_value=_fake_response({"id": "7"}, 1)) as m:
        data = _call_tool(server, "dooray_api_call", {
            "method": "POST",
            "path": "/project/v1/projects/is-creatable",
            "body_json": '{"code": "new-project"}',
        })
    assert data["result"] == {"id": "7"}
    assert m.call_args[1]["json"] == {"code": "new-project"}


def test_api_call_invalid_json(server):
    data = _call_tool(server, "dooray_api_call", {
        "method": "GET",
        "path": "/wiki/v1/wikis",
        "params_json": "{잘못된 json",
    })
    assert data.get("error") is True
