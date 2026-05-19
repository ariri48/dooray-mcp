"""Dooray MCP Server — 두레이 태스크 관리를 위한 Model Context Protocol 서버

Phase 1: 핵심 CRUD (list_tasks, get_task, create_task, update_task, add_comment, list_tags, list_members)
Phase 2: 업무 자동화 (move_task, upload_file, list_workflows, list_milestones, get_comments, delete_task, send_webhook)
Phase 3: Resource 프로바이더 (projects, tags, tenant-config)

보안:
- API 토큰은 .env에서만 로드 (하드코딩 금지)
- 모든 입력값은 validators.py에서 검증
- 위험 작업(삭제)은 확인 메시지 포함
- Rate limiting 내장

데이터 신뢰:
- 모든 API 응답은 구조 검증 후 반환
- 필수 필드 누락 시 명확한 한글 에러
- 사용자 표시용 데이터 정제 (ID → 이름)
"""

from __future__ import annotations

import json
import logging
import os
import sys

from mcp.server.fastmcp import FastMCP

from .client import DoorayClient
from .validators import (
    ValidationError, clean_task_for_display, danger_summary,
    validate_json_array, validate_subjects_list,
)
from .projects import (
    list_all_projects as _list_registered_projects,
    register_project,
    unregister_project,
)
from .audit import log_action

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("dooray-mcp")

# MCP 서버 초기화
mcp = FastMCP("Dooray MCP")

# 클라이언트 lazy 초기화
_client: DoorayClient | None = None


def get_client() -> DoorayClient:
    global _client
    if _client is None:
        _client = DoorayClient()
    return _client


def _error_response(e: Exception) -> str:
    """에러를 사용자 친화적 JSON 문자열로 변환"""
    return json.dumps(
        {"error": True, "message": str(e)},
        ensure_ascii=False,
        indent=2,
    )


def _success_response(data) -> str:
    """성공 응답을 JSON 문자열로 변환"""
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


# ═══════════════════════════════════════════════════════════
# Phase 1: 핵심 CRUD Tools
# ═══════════════════════════════════════════════════════════


@mcp.tool()
def dooray_list_tasks(
    project_id: str = "",
    page: int = 0,
    size: int = 50,
    keyword: str = "",
) -> str:
    """두레이 프로젝트의 태스크 목록을 조회합니다.

    Args:
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트 사용)
        page: 페이지 번호 (0부터 시작)
        size: 한 페이지당 태스크 수 (1~100, 기본 50)
        keyword: 제목 검색 키워드 (지정 시 전체 태스크에서 제목 검색)

    Returns:
        태스크 목록 (제목, 상태, 담당자, 태그 포함)
    """
    try:
        client = get_client()
        result = client.list_tasks(
            project_id or None, page, size,
            keyword=keyword if keyword else None,
        )
        # 사용자 친화적으로 정제
        result["tasks"] = [clean_task_for_display(t) for t in result["tasks"]]
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"list_tasks 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_get_task(
    post_id: str,
    project_id: str = "",
) -> str:
    """두레이 태스크의 상세 정보를 조회합니다. 본문, 담당자, 태그, 첨부파일 등 전체 정보를 반환합니다.

    Args:
        post_id: 태스크 ID (필수)
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트 사용)
    """
    try:
        client = get_client()
        task = client.get_task(post_id, project_id or None)
        cleaned = clean_task_for_display(task)
        cleaned["link"] = client.task_link(post_id)
        # 첨부파일 정보 포함
        files = task.get("_files", [])
        if files:
            cleaned["첨부파일"] = files
            cleaned["첨부파일수"] = len(files)
        else:
            cleaned["첨부파일"] = []
            cleaned["첨부파일수"] = 0
        return _success_response(cleaned)
    except (ValidationError, Exception) as e:
        logger.error(f"get_task 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_create_task(
    subject: str,
    body_md: str = "",
    project_id: str = "",
    tag_names: str = "",
    parent_post_id: str = "",
    workflow_id: str = "",
    milestone_id: str = "",
    assignee_ids: str = "",
    due_date: str = "",
    priority: str = "none",
) -> str:
    """두레이에 새 태스크를 생성합니다.

    Args:
        subject: 태스크 제목 (필수)
        body_md: 본문 내용 (마크다운)
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
        tag_names: 태그 이름 (쉼표 구분, 예: "리셀링,Notification")
        parent_post_id: 상위 태스크 ID (하위 태스크로 생성 시)
        workflow_id: 워크플로우(상태) ID
        milestone_id: 마일스톤(단계) ID
        assignee_ids: 담당자 멤버 ID (쉼표 구분)
        due_date: 마감일 (ISO 형식, 예: "2026-03-31T00:00:00+09:00")
        priority: 우선순위 (none, low, normal, high, urgent)

    Returns:
        생성된 태스크 ID, 제목, dooray:// 링크
    """
    try:
        client = get_client()
        tags = [t.strip() for t in tag_names.split(",") if t.strip()] if tag_names else None
        assignees = [a.strip() for a in assignee_ids.split(",") if a.strip()] if assignee_ids else None

        result = client.create_task(
            subject=subject,
            body_md=body_md,
            project_id=project_id or None,
            tag_names=tags,
            parent_post_id=parent_post_id or None,
            workflow_id=workflow_id or None,
            milestone_id=milestone_id or None,
            assignee_ids=assignees,
            due_date=due_date or None,
            priority=priority,
        )
        log_action("create_task", result.get("id", ""), {"subject": subject}, project_id)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"create_task 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_update_task(
    post_id: str,
    project_id: str = "",
    subject: str = "",
    body_md: str = "",
    workflow_id: str = "",
    milestone_id: str = "",
    tag_names: str = "",
    assignee_ids: str = "",
    cc_ids: str = "",
) -> str:
    """두레이 태스크를 수정합니다. 변경할 필드만 입력하세요.

    Args:
        post_id: 태스크 ID (필수)
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
        subject: 새 제목 (빈 문자열이면 변경 안함)
        body_md: 새 본문 (마크다운, 빈 문자열이면 변경 안함)
        workflow_id: 새 워크플로우(상태) ID
        milestone_id: 새 마일스톤(단계) ID
        tag_names: 새 태그 이름 (쉼표 구분, 기존 태그를 대체)
        assignee_ids: 담당자 멤버 ID (쉼표 구분, 기존 담당자를 대체)
        cc_ids: 참조자 멤버 ID (쉼표 구분, 기존 참조자를 대체)

    Returns:
        변경사항 요약
    """
    try:
        client = get_client()
        tags = [t.strip() for t in tag_names.split(",") if t.strip()] if tag_names else None
        assignees = [a.strip() for a in assignee_ids.split(",") if a.strip()] if assignee_ids else None
        ccs = [c.strip() for c in cc_ids.split(",") if c.strip()] if cc_ids else None

        result = client.update_task(
            post_id=post_id,
            project_id=project_id or None,
            subject=subject if subject else None,
            body_md=body_md if body_md else None,
            workflow_id=workflow_id or None,
            milestone_id=milestone_id or None,
            tag_names=tags,
            assignee_ids=assignees,
            cc_ids=ccs,
        )
        log_action("update_task", post_id, {"changes": result.get("변경사항", [])}, project_id)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"update_task 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_add_comment(
    post_id: str,
    content_md: str,
    project_id: str = "",
) -> str:
    """두레이 태스크에 코멘트(댓글)를 추가합니다.

    Args:
        post_id: 태스크 ID (필수)
        content_md: 코멘트 내용 (마크다운 지원)
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
    """
    try:
        client = get_client()
        result = client.add_comment(post_id, content_md, project_id or None)
        log_action("add_comment", post_id, {"length": len(content_md)}, project_id)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"add_comment 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_list_tags(
    project_id: str = "",
) -> str:
    """두레이 프로젝트의 태그 목록을 조회합니다.

    태그 이름으로 태스크를 생성/수정할 때 참고하세요.

    Args:
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
    """
    try:
        client = get_client()
        tags = client.list_tags(project_id or None)
        return _success_response({"tags": tags, "총_태그수": len(tags)})
    except (ValidationError, Exception) as e:
        logger.error(f"list_tags 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_list_members(
    project_id: str = "",
) -> str:
    """두레이 프로젝트의 멤버(담당자) 목록을 조회합니다.

    담당자를 지정할 때 멤버 ID를 확인하세요.

    Args:
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
    """
    try:
        client = get_client()
        members = client.list_members(project_id or None)
        return _success_response({"members": members, "총_멤버수": len(members)})
    except (ValidationError, Exception) as e:
        logger.error(f"list_members 실패: {e}")
        return _error_response(e)


# ═══════════════════════════════════════════════════════════
# Phase 2: 업무 자동화 Tools
# ═══════════════════════════════════════════════════════════


@mcp.tool()
def dooray_move_task(
    post_id: str,
    parent_post_id: str,
    project_id: str = "",
) -> str:
    """태스크를 다른 상위 태스크 아래로 이동합니다.

    [주의] 태스크의 위치가 변경됩니다.

    Args:
        post_id: 이동할 태스크 ID (필수)
        parent_post_id: 새 상위 태스크 ID (필수)
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
    """
    try:
        client = get_client()
        result = client.move_task(post_id, parent_post_id, project_id or None)
        log_action("move_task", post_id, {"parent": parent_post_id}, project_id)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"move_task 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_upload_file(
    post_id: str,
    file_path: str,
    project_id: str = "",
) -> str:
    """두레이 태스크에 파일을 첨부합니다.

    Args:
        post_id: 태스크 ID (필수)
        file_path: 업로드할 파일의 로컬 경로 (필수)
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
    """
    try:
        client = get_client()
        result = client.upload_file(post_id, file_path, project_id or None)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"upload_file 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_copy_files(
    source_post_id: str,
    target_post_id: str,
    source_project_id: str = "",
    target_project_id: str = "",
    file_ids: str = "",
) -> str:
    """태스크 간 첨부파일을 복사합니다. (다운로드 → 재업로드)

    원본 태스크의 첨부파일을 대상 태스크로 복사합니다.
    file_ids를 지정하면 특정 파일만, 미지정 시 전체 파일을 복사합니다.

    Args:
        source_post_id: 원본 태스크 ID (필수)
        target_post_id: 대상 태스크 ID (필수)
        source_project_id: 원본 프로젝트 ID (미지정 시 기본 프로젝트)
        target_project_id: 대상 프로젝트 ID (미지정 시 기본 프로젝트)
        file_ids: 복사할 파일 ID (쉼표 구분, 미지정 시 전체)
    """
    try:
        client = get_client()
        fids = [f.strip() for f in file_ids.split(",") if f.strip()] if file_ids else None

        result = client.copy_files_between_tasks(
            source_post_id=source_post_id,
            target_post_id=target_post_id,
            source_project_id=source_project_id or None,
            target_project_id=target_project_id or None,
            file_ids=fids,
        )
        log_action("copy_files", target_post_id, {
            "source": source_post_id,
            "copied": len(result.get("복사_성공", [])),
        }, target_project_id)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"copy_files 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_list_workflows(
    project_id: str = "",
) -> str:
    """두레이 프로젝트의 워크플로우(상태) 목록을 조회합니다.

    태스크 상태를 변경할 때 워크플로우 ID를 확인하세요.
    예: "진행중", "파트너(활성)", "해지" 등

    Args:
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
    """
    try:
        client = get_client()
        workflows = client.list_workflows(project_id or None)
        return _success_response({"workflows": workflows, "총_워크플로우수": len(workflows)})
    except (ValidationError, Exception) as e:
        logger.error(f"list_workflows 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_list_milestones(
    project_id: str = "",
) -> str:
    """두레이 프로젝트의 마일스톤(단계) 목록을 조회합니다.

    태스크 단계를 변경할 때 마일스톤 ID를 확인하세요.
    예: "인입", "정책안내", "계약서-Slam", "완료" 등

    Args:
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
    """
    try:
        client = get_client()
        milestones = client.list_milestones(project_id or None)
        return _success_response({"milestones": milestones, "총_마일스톤수": len(milestones)})
    except (ValidationError, Exception) as e:
        logger.error(f"list_milestones 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_get_comments(
    post_id: str,
    project_id: str = "",
    page: int = 0,
    size: int = 50,
) -> str:
    """두레이 태스크의 코멘트(댓글) 목록을 조회합니다.

    Args:
        post_id: 태스크 ID (필수)
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
        page: 페이지 번호 (0부터 시작)
        size: 한 페이지당 코멘트 수 (1~100, 기본 50)
    """
    try:
        client = get_client()
        comments = client.get_comments(post_id, project_id or None, page, size)
        return _success_response({"comments": comments, "총_코멘트수": len(comments)})
    except (ValidationError, Exception) as e:
        logger.error(f"get_comments 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_delete_task(
    post_id: str,
    project_id: str = "",
    confirm: bool = False,
) -> str:
    """두레이 태스크를 삭제합니다.

    [경고] 이 작업은 되돌릴 수 없습니다!
    삭제 전 confirm=true를 명시적으로 전달해야 합니다.

    Args:
        post_id: 삭제할 태스크 ID (필수)
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
        confirm: 삭제 확인 (true여야 실제 삭제 실행)
    """
    try:
        client = get_client()

        if not confirm:
            # 삭제 전 확인: 태스크 정보만 조회하여 보여줌
            task = client.get_task(post_id, project_id or None)
            summary = danger_summary(
                action="태스크 삭제",
                target=f"{task.get('subject', '?')} ({post_id})",
                details={
                    "상태": task.get("workflowClass", "알 수 없음"),
                    "태그": ", ".join(
                        t.get("name", "") for t in task.get("tags", [])
                    ),
                },
            )
            return _success_response({
                "confirm_required": True,
                "message": summary,
                "안내": "삭제를 진행하려면 confirm=true로 다시 호출하세요.",
            })

        result = client.delete_task(post_id, project_id or None)
        log_action("delete_task", post_id, {"subject": result.get("삭제된_태스크", "")}, project_id)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"delete_task 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_send_webhook(
    message: str,
    bot_name: str = "Dooray MCP",
) -> str:
    """Dooray Messenger로 웹훅 알림을 발송합니다.

    Args:
        message: 발송할 메시지 내용 (필수)
        bot_name: 봇 표시 이름 (기본: "Dooray MCP")
    """
    try:
        client = get_client()
        result = client.send_webhook(message, bot_name)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"send_webhook 실패: {e}")
        return _error_response(e)


# ═══════════════════════════════════════════════════════════
# Phase 3: Resource 프로바이더
# ═══════════════════════════════════════════════════════════


@mcp.resource("dooray://tenant-config")
def get_tenant_config() -> str:
    """현재 Dooray 설정 정보를 반환합니다 (토큰 제외).

    테넌트 ID, 기본 프로젝트 ID, 링크 형식 등을 확인할 수 있습니다.
    """
    client = get_client()
    config = {
        "tenant_id": client.tenant_id,
        "default_project_id": client.default_project_id or "(미설정)",
        "webhook_configured": bool(client.webhook_url),
        "link_format": f"dooray://{client.tenant_id}/tasks/{{post_id}}",
        "mention_format": f'[@이름](dooray://{client.tenant_id}/members/{{member_id}} "member")',
        "api_base_url": client.BASE_URL,
    }
    return json.dumps(config, ensure_ascii=False, indent=2)


@mcp.resource("dooray://projects/{project_id}/tags")
def get_project_tags(project_id: str) -> str:
    """프로젝트의 전체 태그 목록을 Resource로 제공합니다.

    태스크 생성/수정 시 태그 이름을 참조하는 데 사용됩니다.
    """
    try:
        client = get_client()
        tags = client.list_tags(project_id)
        return json.dumps(
            {"project_id": project_id, "tags": tags, "총_태그수": len(tags)},
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.resource("dooray://projects/{project_id}/workflows")
def get_project_workflows(project_id: str) -> str:
    """프로젝트의 워크플로우(상태) 목록을 Resource로 제공합니다."""
    try:
        client = get_client()
        workflows = client.list_workflows(project_id)
        return json.dumps(
            {"project_id": project_id, "workflows": workflows},
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.resource("dooray://projects/{project_id}/milestones")
def get_project_milestones(project_id: str) -> str:
    """프로젝트의 마일스톤(단계) 목록을 Resource로 제공합니다."""
    try:
        client = get_client()
        milestones = client.list_milestones(project_id)
        return json.dumps(
            {"project_id": project_id, "milestones": milestones},
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.resource("dooray://projects/{project_id}/members")
def get_project_members(project_id: str) -> str:
    """프로젝트의 멤버 목록을 Resource로 제공합니다."""
    try:
        client = get_client()
        members = client.list_members(project_id)
        return json.dumps(
            {"project_id": project_id, "members": members},
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════
# Phase 4: 팀 확장 Tools
# ═══════════════════════════════════════════════════════════


@mcp.tool()
def dooray_list_projects() -> str:
    """등록된 프로젝트 별칭 목록을 보여줍니다.

    프로젝트 이름(별칭)으로 다른 Tool을 호출할 수 있습니다.
    예: dooray_list_tasks(project_id="파트너신청")

    별칭이 없으면 dooray_discover_projects를 먼저 실행하세요.
    """
    try:
        projects = _list_registered_projects()
        if not projects:
            return _success_response({
                "projects": [],
                "안내": "등록된 프로젝트가 없습니다. dooray_discover_projects를 실행하여 자동 등록하세요.",
            })
        return _success_response({"projects": projects, "총_프로젝트수": len(projects)})
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def dooray_discover_projects(auto_register: bool = True) -> str:
    """Dooray API에서 접근 가능한 프로젝트를 자동 탐색합니다.

    auto_register=true이면 탐색된 프로젝트를 projects.json에 자동 등록합니다.
    프로젝트 이름이 별칭으로 사용됩니다.

    Args:
        auto_register: 탐색된 프로젝트를 자동 등록할지 여부 (기본: true)
    """
    try:
        client = get_client()
        discovered = client.discover_projects()

        if auto_register:
            registered = []
            for p in discovered:
                if p["id"] and p["name"] and p.get("state") != "deleted":
                    info = register_project(
                        alias=p["name"],
                        project_id=p["id"],
                        description=p.get("description", "") or p.get("code", ""),
                    )
                    registered.append(info)
            return _success_response({
                "탐색됨": len(discovered),
                "등록됨": len(registered),
                "projects": registered,
                "안내": "이제 프로젝트 이름으로 태스크를 조회할 수 있습니다. 예: dooray_list_tasks(project_id='프로젝트이름')",
            })

        return _success_response({
            "탐색됨": len(discovered),
            "projects": discovered,
        })
    except (ValidationError, Exception) as e:
        logger.error(f"discover_projects 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_register_project(
    alias: str,
    project_id: str,
    description: str = "",
) -> str:
    """프로젝트 별칭을 수동으로 등록합니다.

    Args:
        alias: 별칭 (예: "파트너신청", "영업대행")
        project_id: Dooray 프로젝트 ID (숫자)
        description: 프로젝트 설명 (선택)
    """
    try:
        result = register_project(alias, project_id, description)
        return _success_response({"message": f"프로젝트 별칭 등록 완료: '{alias}'", **result})
    except (ValidationError, Exception) as e:
        return _error_response(e)


@mcp.tool()
def dooray_my_tasks(
    project_id: str = "",
) -> str:
    """나에게 배정된 태스크만 조회합니다.

    현재 API 토큰 소유자가 담당자로 지정된 태스크만 필터링합니다.

    Args:
        project_id: 프로젝트 ID 또는 별칭 (미지정 시 기본 프로젝트)
    """
    try:
        client = get_client()
        tasks = client.list_my_tasks(project_id or None)
        cleaned = [clean_task_for_display(t) for t in tasks]
        return _success_response({
            "내_태스크": cleaned,
            "총_건수": len(cleaned),
        })
    except (ValidationError, Exception) as e:
        logger.error(f"my_tasks 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_search_tasks(
    project_id: str = "",
    keyword: str = "",
    tag_name: str = "",
    assignee_name: str = "",
    workflow_class: str = "",
) -> str:
    """태스크를 복합 조건으로 검색합니다.

    모든 조건은 AND로 결합됩니다. 하나 이상의 조건을 지정하세요.

    Args:
        project_id: 프로젝트 ID 또는 별칭
        keyword: 제목 검색어
        tag_name: 태그 이름 (정확히 일치)
        assignee_name: 담당자 이름 (부분 일치)
        workflow_class: 워크플로우 분류 (예: "registered", "working", "closed")
    """
    try:
        client = get_client()
        all_tasks = client.list_all_tasks(project_id or None)
        results = all_tasks

        if keyword and keyword.strip():
            kw = keyword.strip().lower()
            results = [t for t in results if kw in t.get("subject", "").lower()]

        if tag_name and tag_name.strip():
            tn = tag_name.strip().lower()
            results = [
                t for t in results
                if any(tn == tag.get("name", "").lower() for tag in t.get("tags", []))
            ]

        if assignee_name and assignee_name.strip():
            an = assignee_name.strip().lower()
            filtered = []
            for t in results:
                for u in t.get("users", {}).get("to", []):
                    name = u.get("member", {}).get("name", "").lower()
                    if an in name:
                        filtered.append(t)
                        break
            results = filtered

        if workflow_class and workflow_class.strip():
            wc = workflow_class.strip().lower()
            results = [
                t for t in results
                if wc in t.get("workflowClass", "").lower()
            ]

        cleaned = [clean_task_for_display(t) for t in results]
        return _success_response({
            "검색결과": cleaned,
            "총_건수": len(cleaned),
            "검색조건": {
                k: v for k, v in {
                    "keyword": keyword, "tag_name": tag_name,
                    "assignee_name": assignee_name, "workflow_class": workflow_class,
                }.items() if v
            },
        })
    except (ValidationError, Exception) as e:
        logger.error(f"search_tasks 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_audit_log(limit: int = 30) -> str:
    """내 최근 활동 기록을 조회합니다.

    로컬에 저장된 쓰기 작업(생성/수정/삭제/코멘트) 이력을 보여줍니다.

    Args:
        limit: 조회할 최대 건수 (기본 30)
    """
    try:
        from .audit import get_recent_logs
        logs = get_recent_logs(limit)
        return _success_response({"logs": logs, "총_건수": len(logs)})
    except Exception as e:
        return _error_response(e)


# ═══════════════════════════════════════════════════════════
# Phase 5: 추가 기능 Tools
# ═══════════════════════════════════════════════════════════


@mcp.tool()
def dooray_update_subject(
    post_id: str,
    new_subject: str,
    project_id: str = "",
) -> str:
    """두레이 태스크의 제목을 변경합니다.

    Args:
        post_id: 태스크 ID (필수)
        new_subject: 새 제목 (필수)
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
    """
    try:
        client = get_client()
        result = client.update_task(
            post_id=post_id,
            project_id=project_id or None,
            subject=new_subject,
        )
        log_action("update_subject", post_id, {"new_subject": new_subject}, project_id)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"update_subject 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_create_subtask(
    parent_post_id: str,
    subjects: str,
    project_id: str = "",
    workflow_id: str = "",
    assignee_ids: str = "",
) -> str:
    """상위 태스크 아래에 하위 태스크를 일괄 생성합니다.

    Args:
        parent_post_id: 상위 태스크 ID (필수)
        subjects: 하위 태스크 제목 목록 (줄바꿈 또는 쉼표로 구분)
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
        workflow_id: 워크플로우(상태) ID
        assignee_ids: 담당자 멤버 ID (쉼표 구분)
    """
    try:
        client = get_client()
        subject_list = validate_subjects_list(subjects)
        assignees = [a.strip() for a in assignee_ids.split(",") if a.strip()] if assignee_ids else None

        result = client.create_subtasks(
            parent_post_id=parent_post_id,
            subjects=subject_list,
            project_id=project_id or None,
            workflow_id=workflow_id or None,
            assignee_ids=assignees,
        )
        log_action("create_subtask", parent_post_id, {"count": len(subject_list)}, project_id)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"create_subtask 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_bulk_create_tasks(
    tasks_json: str,
    project_id: str = "",
) -> str:
    """태스크를 일괄 생성합니다. JSON 배열 형식으로 입력하세요.

    각 항목에 subject(필수), body_md, tag_names(리스트), workflow_id, assignee_ids(리스트) 가능.

    Args:
        tasks_json: 태스크 정의 JSON 배열 (예: [{"subject": "태스크1"}, {"subject": "태스크2", "tag_names": ["태그"]}])
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
    """
    try:
        client = get_client()
        task_defs = validate_json_array(tasks_json, "tasks_json")

        result = client.bulk_create_tasks(
            tasks=task_defs,
            project_id=project_id or None,
        )
        log_action("bulk_create_tasks", "", {"count": len(task_defs)}, project_id)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"bulk_create_tasks 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_list_templates(
    project_id: str = "",
) -> str:
    """두레이 프로젝트의 템플릿 목록을 조회합니다.

    새 업무 생성 시 사용할 수 있는 템플릿을 확인할 수 있습니다.

    Args:
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
    """
    try:
        client = get_client()
        templates = client.list_templates(project_id or None)
        return _success_response({"templates": templates, "총_템플릿수": len(templates)})
    except (ValidationError, Exception) as e:
        logger.error(f"list_templates 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_download_file(
    post_id: str,
    file_id: str,
    file_name: str,
    project_id: str = "",
) -> str:
    """두레이 태스크의 첨부파일을 로컬에 다운로드합니다.

    Args:
        post_id: 태스크 ID (필수)
        file_id: 파일 ID (필수, dooray_get_task로 확인)
        file_name: 파일명 (필수)
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)

    Returns:
        다운로드된 로컬 파일 경로
    """
    try:
        client = get_client()
        local_path = client.download_file(
            post_id=post_id,
            file_id=file_id,
            file_name=file_name,
            project_id=project_id or None,
        )
        return _success_response({
            "로컬경로": local_path,
            "파일명": file_name,
            "message": f"파일 다운로드 완료: {file_name}",
        })
    except (ValidationError, Exception) as e:
        logger.error(f"download_file 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_register_partner(
    source_post_id: str,
    source_project_id: str = "",
    partner_name: str = "",
    skip_file_copy: bool = False,
) -> str:
    """파트너 태스크에서 거래처 등록 태스크를 자동 생성합니다. (원클릭)

    원본 파트너 태스크를 조회하여:
    1. 파트너명/NCA 계정 정보 자동 추출
    2. 클라우드지원팀 프로젝트에 거래처 등록 태스크 생성
    3. 담당자(김난우), 참조(김제홍, 황미현) 자동 지정
    4. 거래처 등록용 첨부파일 4종 자동 복사

    Args:
        source_post_id: 원본 파트너 태스크 ID (필수)
        source_project_id: 원본 프로젝트 ID (기본: 파트너-신청-등록)
        partner_name: 파트너명 (미입력 시 원본 태스크에서 자동 추출)
        skip_file_copy: 첨부파일 복사 건너뛰기 (기본: false)
    """
    try:
        client = get_client()
        result = client.register_partner(
            source_post_id=source_post_id,
            source_project_id=source_project_id or None,
            partner_name=partner_name or None,
            skip_file_copy=skip_file_copy,
        )
        log_action("register_partner", result["거래처등록_태스크"], {
            "source": source_post_id,
            "partner": result["파트너명"],
        })
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"register_partner 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_batch_update(
    post_ids: str,
    project_id: str = "",
    workflow_id: str = "",
    milestone_id: str = "",
    tag_names: str = "",
) -> str:
    """여러 태스크를 동일한 조건으로 일괄 수정합니다.

    Args:
        post_ids: 태스크 ID 목록 (쉼표 구분, 필수)
        project_id: 프로젝트 ID (미지정 시 기본 프로젝트)
        workflow_id: 새 워크플로우(상태) ID
        milestone_id: 새 마일스톤(단계) ID
        tag_names: 새 태그 이름 (쉼표 구분)
    """
    try:
        client = get_client()
        ids = [p.strip() for p in post_ids.split(",") if p.strip()]
        if not ids:
            raise ValidationError("post_ids가 비어있습니다.")
        tags = [t.strip() for t in tag_names.split(",") if t.strip()] if tag_names else None

        result = client.batch_update_tasks(
            post_ids=ids,
            project_id=project_id or None,
            workflow_id=workflow_id or None,
            milestone_id=milestone_id or None,
            tag_names=tags,
        )
        log_action("batch_update", "", {"count": len(ids)}, project_id)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"batch_update 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_clone_task(
    source_post_id: str,
    source_project_id: str = "",
    target_project_id: str = "",
    new_subject: str = "",
    copy_attachments: bool = True,
) -> str:
    """태스크를 복제합니다. (제목, 본문, 태그, 담당자, 첨부파일)

    Args:
        source_post_id: 원본 태스크 ID (필수)
        source_project_id: 원본 프로젝트 ID (미지정 시 기본 프로젝트)
        target_project_id: 대상 프로젝트 ID (미지정 시 원본과 동일)
        new_subject: 새 제목 (미입력 시 "[복사] 원본제목")
        copy_attachments: 첨부파일도 복사할지 여부 (기본: true)
    """
    try:
        client = get_client()
        result = client.clone_task(
            source_post_id=source_post_id,
            source_project_id=source_project_id or None,
            target_project_id=target_project_id or None,
            new_subject=new_subject or None,
            copy_attachments=copy_attachments,
        )
        log_action("clone_task", result["새_태스크_id"], {
            "source": source_post_id,
            "subject": result["제목"],
        })
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"clone_task 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_partner_status(
    project_id: str = "",
    include_tasks: bool = False,
) -> str:
    """파트너 신청 파이프라인 단계별 현황을 보여줍니다.

    인입 → 정책안내 → 법무검토 → 계약서-Slam → 사업기안 → 날인 → 완료 순으로
    각 단계의 건수와 진행중인 태스크를 요약합니다.

    Args:
        project_id: 프로젝트 ID (기본: 파트너-신청-등록)
        include_tasks: 각 단계의 태스크 상세 포함 여부 (기본: false)
    """
    try:
        client = get_client()
        result = client.get_partner_pipeline_status(project_id or None)

        # include_tasks=False면 태스크 상세 제거 (건수만)
        if not include_tasks:
            for stage in result.get("파이프라인", []):
                stage.pop("태스크", None)

        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"partner_status 실패: {e}")
        return _error_response(e)


# ═══════════════════════════════════════════════════════════
# Phase 6: 보고 / 현황관리 / 누락방지
# ═══════════════════════════════════════════════════════════


@mcp.tool()
def dooray_project_summary(
    project_id: str = "",
) -> str:
    """프로젝트 전체 현황을 집계합니다.

    상태별, 마일스톤별, 담당자별, 태그별 건수를 한눈에 보여줍니다.
    주간보고나 현황 파악에 활용하세요.

    Args:
        project_id: 프로젝트 ID 또는 별칭 (미지정 시 기본 프로젝트)
    """
    try:
        client = get_client()
        result = client.project_summary(project_id or None)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"project_summary 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_weekly_report(
    project_id: str = "",
    days: int = 7,
) -> str:
    """주간보고용 변경사항을 요약합니다.

    최근 N일간 신규 생성, 수정, 완료된 태스크를 분류하여 보여줍니다.
    주간보고 취합 시 이 결과를 기반으로 보고서를 작성할 수 있습니다.

    Args:
        project_id: 프로젝트 ID 또는 별칭
        days: 조회 기간 (기본 7일, 주간보고)
    """
    try:
        client = get_client()
        result = client.get_weekly_changes(project_id or None, days)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"weekly_report 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_find_stale_tasks(
    project_id: str = "",
    days: int = 7,
) -> str:
    """오래된 진행중 태스크를 찾습니다 (누락 방지).

    지정 기간 이상 업데이트가 없는 진행중 태스크를 찾아 알려줍니다.
    "이거 잊고 있던 거 아니야?" 체크용입니다.

    Args:
        project_id: 프로젝트 ID 또는 별칭
        days: 경과 일수 기준 (기본 7일)
    """
    try:
        client = get_client()
        stale = client.find_stale_tasks(project_id or None, days)
        cleaned = [clean_task_for_display(t) for t in stale]
        return _success_response({
            "방치된_태스크": cleaned,
            "기준": f"{days}일 이상 변경 없음",
            "총_건수": len(cleaned),
        })
    except (ValidationError, Exception) as e:
        logger.error(f"find_stale_tasks 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_audit_quality(
    project_id: str = "",
) -> str:
    """태스크 품질을 점검합니다.

    담당자 미지정, 본문 비어있음, 태그 없음, 마일스톤 없음 등
    누락된 항목을 찾아 알려줍니다.

    Args:
        project_id: 프로젝트 ID 또는 별칭
    """
    try:
        client = get_client()
        result = client.audit_task_quality(project_id or None)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"audit_quality 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_find_duplicates(
    project_id: str = "",
) -> str:
    """프로젝트 내 중복 태스크를 찾습니다.

    제목을 정규화(날짜 접두사, 대괄호 제거)하여 비교합니다.
    같은 파트너/고객에 대해 태스크가 여러 개 만들어진 경우를 탐지합니다.

    Args:
        project_id: 프로젝트 ID 또는 별칭
    """
    try:
        client = get_client()
        duplicates = client.find_duplicates(project_id or None)
        return _success_response({
            "중복_그룹": duplicates,
            "총_그룹수": len(duplicates),
        })
    except (ValidationError, Exception) as e:
        logger.error(f"find_duplicates 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_parse_body(
    post_id: str,
    project_id: str = "",
) -> str:
    """태스크 본문에서 구조화된 데이터를 추출합니다.

    마크다운 테이블, key:value 패턴, 체크박스, 이메일, 사업자등록번호, URL 등을 자동 파싱합니다.
    "이 태스크에서 파트너명이랑 사업자번호 뽑아줘" 같은 요청에 사용합니다.

    Args:
        post_id: 태스크 ID (필수)
        project_id: 프로젝트 ID 또는 별칭
    """
    try:
        client = get_client()
        result = client.parse_task_body(post_id, project_id or None)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"parse_body 실패: {e}")
        return _error_response(e)


@mcp.tool()
def dooray_search_all_projects(
    keyword: str,
    project_ids: str = "",
) -> str:
    """여러 프로젝트에서 동시에 검색합니다.

    프로젝트를 지정하지 않으면 등록된 전체 프로젝트(최대 20개)에서 검색합니다.

    Args:
        keyword: 검색어 (필수)
        project_ids: 검색할 프로젝트 ID/별칭 (쉼표 구분, 미지정 시 전체)
    """
    try:
        client = get_client()
        pids = [p.strip() for p in project_ids.split(",") if p.strip()] if project_ids else None
        result = client.search_across_projects(keyword, pids)
        return _success_response(result)
    except (ValidationError, Exception) as e:
        logger.error(f"search_all_projects 실패: {e}")
        return _error_response(e)


# ═══════════════════════════════════════════════════════════
# 서버 실행
# ═══════════════════════════════════════════════════════════


def main():
    """MCP 서버 시작"""
    logger.info("Dooray MCP Server 시작...")
    mcp.run()


if __name__ == "__main__":
    main()
