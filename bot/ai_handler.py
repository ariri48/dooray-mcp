"""Claude AI 핸들러 - 자연어 요청을 MCP Tool로 처리

/ai 파트너 A사 태스크를 계약완료로 변경해줘
→ Claude API → search_tasks("A사") → update_task(workflow_id=...)

Claude API 키가 없으면 비활성화 (슬래시 명령만 동작).
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from src.client import DoorayClient
from src.validators import ValidationError, clean_task_for_display

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Tool 정의 (Claude API tool_use 형식)
TOOLS = [
    {
        "name": "dooray_list_tasks",
        "description": "프로젝트 태스크 목록 조회",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "프로젝트 ID 또는 별칭"},
                "keyword": {"type": "string", "description": "제목 검색 키워드"},
            },
        },
    },
    {
        "name": "dooray_get_task",
        "description": "단일 태스크 상세 조회",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "string", "description": "태스크 ID"},
                "project_id": {"type": "string", "description": "프로젝트 ID"},
            },
            "required": ["post_id"],
        },
    },
    {
        "name": "dooray_search_tasks",
        "description": "태스크 복합 검색 (키워드, 태그, 담당자, 상태)",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "keyword": {"type": "string"},
                "tag_name": {"type": "string"},
                "assignee_name": {"type": "string"},
            },
        },
    },
    {
        "name": "dooray_my_tasks",
        "description": "나에게 배정된 태스크 조회",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
            },
        },
    },
    {
        "name": "dooray_project_summary",
        "description": "프로젝트 현황 집계 (상태별/담당자별/태그별)",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
            },
        },
    },
    {
        "name": "dooray_weekly_report",
        "description": "주간보고용 변경사항 요약 (신규/수정/완료)",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "days": {"type": "integer", "default": 7},
            },
        },
    },
    {
        "name": "dooray_find_stale_tasks",
        "description": "방치된 태스크 찾기",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "days": {"type": "integer", "default": 7},
            },
        },
    },
    {
        "name": "dooray_create_task",
        "description": "새 태스크 생성",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "태스크 제목"},
                "body_md": {"type": "string", "description": "본문 (마크다운)"},
                "project_id": {"type": "string"},
                "tag_names": {"type": "string", "description": "태그 (쉼표 구분)"},
            },
            "required": ["subject"],
        },
    },
    {
        "name": "dooray_update_task",
        "description": "태스크 수정 (상태, 마일스톤, 태그, 담당자 변경)",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "string"},
                "project_id": {"type": "string"},
                "workflow_id": {"type": "string"},
                "milestone_id": {"type": "string"},
                "tag_names": {"type": "string"},
            },
            "required": ["post_id"],
        },
    },
    {
        "name": "dooray_add_comment",
        "description": "태스크에 코멘트 추가",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "string"},
                "content_md": {"type": "string"},
                "project_id": {"type": "string"},
            },
            "required": ["post_id", "content_md"],
        },
    },
]


def _execute_tool(tool_name: str, tool_input: dict) -> str:
    """MCP Tool을 직접 실행하고 결과 반환."""
    client = DoorayClient()

    try:
        if tool_name == "dooray_list_tasks":
            result = client.list_tasks(
                project_id=tool_input.get("project_id") or None,
                keyword=tool_input.get("keyword") or None,
            )
            result["tasks"] = [clean_task_for_display(t) for t in result["tasks"]]
        elif tool_name == "dooray_get_task":
            task = client.get_task(tool_input["post_id"], tool_input.get("project_id"))
            result = clean_task_for_display(task)
        elif tool_name == "dooray_search_tasks":
            all_tasks = client.list_all_tasks(tool_input.get("project_id") or None)
            results = all_tasks
            if tool_input.get("keyword"):
                kw = tool_input["keyword"].lower()
                results = [t for t in results if kw in t.get("subject", "").lower()]
            if tool_input.get("tag_name"):
                tn = tool_input["tag_name"].lower()
                results = [t for t in results if any(tn == tag.get("name", "").lower() for tag in t.get("tags", []))]
            if tool_input.get("assignee_name"):
                an = tool_input["assignee_name"].lower()
                results = [t for t in results if any(an in u.get("member", {}).get("name", "").lower() for u in t.get("users", {}).get("to", []))]
            result = {"검색결과": [clean_task_for_display(t) for t in results[:20]], "총_건수": len(results)}
        elif tool_name == "dooray_my_tasks":
            tasks = client.list_my_tasks(tool_input.get("project_id") or None)
            result = {"내_태스크": [clean_task_for_display(t) for t in tasks], "총_건수": len(tasks)}
        elif tool_name == "dooray_project_summary":
            result = client.project_summary(tool_input.get("project_id") or None)
        elif tool_name == "dooray_weekly_report":
            result = client.get_weekly_changes(tool_input.get("project_id") or None, tool_input.get("days", 7))
        elif tool_name == "dooray_find_stale_tasks":
            stale = client.find_stale_tasks(tool_input.get("project_id") or None, tool_input.get("days", 7))
            result = {"방치된_태스크": [clean_task_for_display(t) for t in stale], "총_건수": len(stale)}
        elif tool_name == "dooray_create_task":
            tags = [t.strip() for t in tool_input.get("tag_names", "").split(",") if t.strip()] if tool_input.get("tag_names") else None
            result = client.create_task(
                subject=tool_input["subject"],
                body_md=tool_input.get("body_md", ""),
                project_id=tool_input.get("project_id") or None,
                tag_names=tags,
            )
        elif tool_name == "dooray_update_task":
            result = client.update_task(
                post_id=tool_input["post_id"],
                project_id=tool_input.get("project_id") or None,
                workflow_id=tool_input.get("workflow_id") or None,
                milestone_id=tool_input.get("milestone_id") or None,
            )
        elif tool_name == "dooray_add_comment":
            result = client.add_comment(
                post_id=tool_input["post_id"],
                content_md=tool_input["content_md"],
                project_id=tool_input.get("project_id") or None,
            )
        else:
            result = {"error": f"알 수 없는 Tool: {tool_name}"}

        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def handle_ai_request(user_message: str) -> str:
    """Claude API로 자연어 요청 처리.

    Returns:
        응답 텍스트 (마크다운)
    """
    if not ANTHROPIC_API_KEY:
        return (
            "AI 모드가 비활성화되어 있습니다.\n"
            ".env에 `ANTHROPIC_API_KEY`를 설정하세요.\n\n"
            "슬래시 명령어는 `/도움말`로 확인하세요."
        )

    try:
        import anthropic
    except ImportError:
        return "anthropic 패키지가 설치되지 않았습니다. `pip install anthropic`을 실행하세요."

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    system_prompt = (
        "당신은 두레이(Dooray) 업무 관리 도우미입니다. "
        "사용자의 요청을 이해하고 적절한 Tool을 호출하여 처리하세요. "
        "응답은 간결한 마크다운으로 작성하세요. "
        "한국어로 답변하세요."
    )

    messages = [{"role": "user", "content": user_message}]

    # Tool use loop (최대 3회)
    for _ in range(3):
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        # 응답에서 텍스트와 tool_use 분리
        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        # Tool 호출이 없으면 텍스트 반환
        if not tool_uses:
            return "\n".join(text_parts) or "처리 완료"

        # Tool 실행 + 결과 피드백
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tool_use in tool_uses:
            result = _execute_tool(tool_use.name, tool_use.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})

    # 최종 응답
    return "\n".join(text_parts) if text_parts else "처리 완료"
