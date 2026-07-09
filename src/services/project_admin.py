"""Project 관리 API — 프로젝트/워크플로우/태그/마일스톤/멤버/템플릿 등

엔드포인트:
- GET  /project/v1/project-categories
- POST /project/v1/projects, GET /project/v1/projects, GET /project/v1/projects/{id}
- POST /project/v1/projects/is-creatable
- 워크플로우: GET/POST/PUT + POST {id}/delete
- 이메일 주소: POST, GET
- 태그: POST, GET 목록/단건, PUT tag-groups/{id}
- 마일스톤: POST/GET/GET/PUT/DELETE
- 훅: POST
- 멤버: POST/GET/GET, 멤버그룹: GET/GET
- 템플릿: POST/GET/GET/PUT/DELETE
"""

from __future__ import annotations

from ..validators import ValidationError
from ._base import err, logger, need_confirm, ok, parse_json, split_ids


def register(mcp, get_client):

    # ── 프로젝트 카테고리 / 프로젝트 ──────────────────────

    @mcp.tool()
    def dooray_project_categories(page: int = 0, size: int = 100) -> str:
        """프로젝트 카테고리 목록을 조회합니다. (GET /project/v1/project-categories)"""
        try:
            result = get_client().api(
                "GET", "/project/v1/project-categories",
                params={"page": page, "size": size}, full=True,
            )
            return ok({"categories": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_project_create(
        code: str,
        description: str = "",
        scope: str = "private",
    ) -> str:
        """새 프로젝트를 생성합니다. (POST /project/v1/projects)

        Args:
            code: 프로젝트 코드(이름, 필수)
            description: 프로젝트 설명
            scope: 공개 범위 (private | public)
        """
        try:
            payload = {"code": code, "description": description, "scope": scope}
            return ok(get_client().api("POST", "/project/v1/projects", payload=payload))
        except Exception as e:
            logger.error(f"project_create 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_project_list_api(
        page: int = 0,
        size: int = 100,
        member: str = "me",
        params_json: str = "",
    ) -> str:
        """접근 가능한 프로젝트 목록을 API로 조회합니다. (GET /project/v1/projects)

        Args:
            page: 페이지 번호
            size: 페이지 크기
            member: 멤버 필터 (기본 "me")
            params_json: 추가 쿼리 파라미터 JSON (예: '{"state": "active"}')
        """
        try:
            params = {"page": page, "size": size, "member": member}
            extra = parse_json(params_json, "params_json", dict)
            if extra:
                params.update(extra)
            result = get_client().api("GET", "/project/v1/projects", params=params, full=True)
            return ok({"projects": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_project_get(project_id: str) -> str:
        """프로젝트 상세 정보를 조회합니다. (GET /project/v1/projects/{project-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            return ok(client.api("GET", f"/project/v1/projects/{pid}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_project_is_creatable(code: str) -> str:
        """프로젝트 코드 사용 가능 여부를 확인합니다. (POST /project/v1/projects/is-creatable)

        Args:
            code: 확인할 프로젝트 코드 (필수)
        """
        try:
            return ok(get_client().api(
                "POST", "/project/v1/projects/is-creatable", payload={"code": code},
            ))
        except Exception as e:
            return err(e)

    # ── 워크플로우 ─────────────────────────────────────────

    @mcp.tool()
    def dooray_workflow_create(
        project_id: str,
        name: str,
        workflow_class: str = "registered",
        order: int = -1,
    ) -> str:
        """프로젝트에 워크플로우(상태)를 추가합니다. (POST /project/v1/projects/{id}/workflows)

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            name: 워크플로우 이름 (필수)
            workflow_class: 분류 (backlog | registered | working | closed)
            order: 정렬 순서 (-1이면 미지정)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            payload = {"name": name, "class": workflow_class}
            if order >= 0:
                payload["order"] = order
            return ok(client.api(
                "POST", f"/project/v1/projects/{pid}/workflows", payload=payload,
            ))
        except Exception as e:
            logger.error(f"workflow_create 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_workflow_update(
        project_id: str,
        workflow_id: str,
        name: str = "",
        workflow_class: str = "",
        order: int = -1,
    ) -> str:
        """워크플로우(상태)를 수정합니다. (PUT /project/v1/projects/{id}/workflows/{workflow-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            workflow_id: 워크플로우 ID (필수)
            name: 새 이름
            workflow_class: 새 분류 (backlog | registered | working | closed)
            order: 정렬 순서 (-1이면 변경 안함)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            payload = {}
            if name:
                payload["name"] = name
            if workflow_class:
                payload["class"] = workflow_class
            if order >= 0:
                payload["order"] = order
            if not payload:
                raise ValidationError("변경할 내용이 없습니다.")
            client.api(
                "PUT", f"/project/v1/projects/{pid}/workflows/{workflow_id}",
                payload=payload,
            )
            return ok({"message": f"워크플로우 수정 완료: {workflow_id}", "변경": payload})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_workflow_delete(
        project_id: str,
        workflow_id: str,
        confirm: bool = False,
    ) -> str:
        """워크플로우(상태)를 삭제합니다. (POST /project/v1/projects/{id}/workflows/{workflow-id}/delete)

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            workflow_id: 삭제할 워크플로우 ID (필수)
            confirm: 삭제 확인 (true여야 실제 삭제)
        """
        try:
            if not confirm:
                return need_confirm("워크플로우 삭제", workflow_id)
            client = get_client()
            pid = client._resolve_project(project_id)
            client.api(
                "POST", f"/project/v1/projects/{pid}/workflows/{workflow_id}/delete",
                payload={},
            )
            return ok({"message": f"워크플로우 삭제 완료: {workflow_id}"})
        except Exception as e:
            return err(e)

    # ── 이메일 주소 ────────────────────────────────────────

    @mcp.tool()
    def dooray_project_add_email_address(
        project_id: str,
        email_address: str,
        name: str = "",
    ) -> str:
        """프로젝트 전용 이메일 주소를 등록합니다. (POST /project/v1/projects/{id}/email-addresses)

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            email_address: 이메일 주소 (필수)
            name: 표시 이름
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            payload = {"emailAddress": email_address}
            if name:
                payload["name"] = name
            return ok(client.api(
                "POST", f"/project/v1/projects/{pid}/email-addresses", payload=payload,
            ))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_project_get_email_address(project_id: str, email_address_id: str) -> str:
        """프로젝트 이메일 주소를 조회합니다. (GET /project/v1/projects/{id}/email-addresses/{email-address-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            email_address_id: 이메일 주소 ID (필수)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            return ok(client.api(
                "GET", f"/project/v1/projects/{pid}/email-addresses/{email_address_id}",
            ))
        except Exception as e:
            return err(e)

    # ── 태그 ───────────────────────────────────────────────

    @mcp.tool()
    def dooray_tag_create(
        project_id: str,
        name: str,
        color: str = "F3F3F3",
    ) -> str:
        """프로젝트에 태그를 생성합니다. (POST /project/v1/projects/{id}/tags)

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            name: 태그 이름 (필수)
            color: 태그 색상 HEX (기본 F3F3F3)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            return ok(client.api(
                "POST", f"/project/v1/projects/{pid}/tags",
                payload={"name": name, "color": color.lstrip("#")},
            ))
        except Exception as e:
            logger.error(f"tag_create 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_tag_get(project_id: str, tag_id: str) -> str:
        """태그 1개의 상세 정보를 조회합니다. (GET /project/v1/projects/{id}/tags/{tag-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            tag_id: 태그 ID (필수)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            return ok(client.api("GET", f"/project/v1/projects/{pid}/tags/{tag_id}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_tag_group_update(
        project_id: str,
        tag_group_id: str,
        body_json: str,
    ) -> str:
        """태그 그룹을 수정합니다. (PUT /project/v1/projects/{id}/tag-groups/{tag-group-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            tag_group_id: 태그 그룹 ID (필수)
            body_json: 수정 바디 JSON (예: '{"name": "우선순위", "mandatory": true}')
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            payload = parse_json(body_json, "body_json", dict)
            if not payload:
                raise ValidationError("body_json이 비어있습니다.")
            client.api(
                "PUT", f"/project/v1/projects/{pid}/tag-groups/{tag_group_id}",
                payload=payload,
            )
            return ok({"message": f"태그 그룹 수정 완료: {tag_group_id}"})
        except Exception as e:
            return err(e)

    # ── 마일스톤 ───────────────────────────────────────────

    @mcp.tool()
    def dooray_milestone_create(
        project_id: str,
        name: str,
        started_at: str = "",
        ended_at: str = "",
    ) -> str:
        """마일스톤을 생성합니다. (POST /project/v1/projects/{id}/milestones)

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            name: 마일스톤 이름 (필수)
            started_at: 시작일 (예: "2026-07-01")
            ended_at: 종료일 (예: "2026-07-31")
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            payload = {"name": name}
            if started_at:
                payload["startedAt"] = started_at
            if ended_at:
                payload["endedAt"] = ended_at
            return ok(client.api(
                "POST", f"/project/v1/projects/{pid}/milestones", payload=payload,
            ))
        except Exception as e:
            logger.error(f"milestone_create 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_milestone_get(project_id: str, milestone_id: str) -> str:
        """마일스톤 상세 정보를 조회합니다. (GET /project/v1/projects/{id}/milestones/{milestone-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            milestone_id: 마일스톤 ID (필수)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            return ok(client.api(
                "GET", f"/project/v1/projects/{pid}/milestones/{milestone_id}",
            ))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_milestone_update(
        project_id: str,
        milestone_id: str,
        name: str = "",
        status: str = "",
        started_at: str = "",
        ended_at: str = "",
    ) -> str:
        """마일스톤을 수정합니다. (PUT /project/v1/projects/{id}/milestones/{milestone-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            milestone_id: 마일스톤 ID (필수)
            name: 새 이름
            status: 상태 (open | closed)
            started_at: 시작일
            ended_at: 종료일
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            payload = {}
            if name:
                payload["name"] = name
            if status:
                payload["status"] = status
            if started_at:
                payload["startedAt"] = started_at
            if ended_at:
                payload["endedAt"] = ended_at
            if not payload:
                raise ValidationError("변경할 내용이 없습니다.")
            client.api(
                "PUT", f"/project/v1/projects/{pid}/milestones/{milestone_id}",
                payload=payload,
            )
            return ok({"message": f"마일스톤 수정 완료: {milestone_id}", "변경": payload})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_milestone_delete(
        project_id: str,
        milestone_id: str,
        confirm: bool = False,
    ) -> str:
        """마일스톤을 삭제합니다. (DELETE /project/v1/projects/{id}/milestones/{milestone-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            milestone_id: 삭제할 마일스톤 ID (필수)
            confirm: 삭제 확인 (true여야 실제 삭제)
        """
        try:
            if not confirm:
                return need_confirm("마일스톤 삭제", milestone_id)
            client = get_client()
            pid = client._resolve_project(project_id)
            client.api("DELETE", f"/project/v1/projects/{pid}/milestones/{milestone_id}")
            return ok({"message": f"마일스톤 삭제 완료: {milestone_id}"})
        except Exception as e:
            return err(e)

    # ── 훅 ─────────────────────────────────────────────────

    @mcp.tool()
    def dooray_project_hook_create(
        project_id: str,
        url: str,
        send_events: str = "",
    ) -> str:
        """프로젝트 이벤트 훅(웹훅)을 등록합니다. (POST /project/v1/projects/{id}/hooks)

        업무 등록/변경/댓글 등 이벤트 발생 시 지정한 URL로 알림을 받습니다.

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            url: 이벤트를 수신할 URL (필수)
            send_events: 수신할 이벤트 (쉼표 구분, 예: "postCreated,postCommentCreated,postWorkflowChanged")
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            payload = {"url": url}
            events = split_ids(send_events)
            if events:
                payload["sendEvents"] = events
            return ok(client.api(
                "POST", f"/project/v1/projects/{pid}/hooks", payload=payload,
            ))
        except Exception as e:
            logger.error(f"project_hook_create 실패: {e}")
            return err(e)

    # ── 멤버 / 멤버 그룹 ───────────────────────────────────

    @mcp.tool()
    def dooray_project_add_members(
        project_id: str,
        member_ids: str,
        role: str = "member",
    ) -> str:
        """프로젝트에 멤버를 추가합니다. (POST /project/v1/projects/{id}/members)

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            member_ids: 조직 멤버 ID (쉼표 구분, 필수)
            role: 역할 (member | admin)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            ids = split_ids(member_ids)
            if not ids:
                raise ValidationError("member_ids가 비어있습니다.")
            payload = [{"organizationMemberId": mid, "role": role} for mid in ids]
            return ok(client.api(
                "POST", f"/project/v1/projects/{pid}/members", payload=payload,
            ))
        except Exception as e:
            logger.error(f"project_add_members 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_project_get_member(project_id: str, member_id: str) -> str:
        """프로젝트 멤버 1명을 조회합니다. (GET /project/v1/projects/{id}/members/{member-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            member_id: 조직 멤버 ID (필수)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            return ok(client.api(
                "GET", f"/project/v1/projects/{pid}/members/{member_id}",
            ))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_member_groups(project_id: str, page: int = 0, size: int = 100) -> str:
        """프로젝트 멤버 그룹 목록을 조회합니다. (GET /project/v1/projects/{id}/member-groups)

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            page: 페이지 번호
            size: 페이지 크기
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            result = client.api(
                "GET", f"/project/v1/projects/{pid}/member-groups",
                params={"page": page, "size": size}, full=True,
            )
            return ok({"memberGroups": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_member_group_get(project_id: str, member_group_id: str) -> str:
        """프로젝트 멤버 그룹 1개를 조회합니다. (GET /project/v1/projects/{id}/member-groups/{member-group-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            member_group_id: 멤버 그룹 ID (필수)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            return ok(client.api(
                "GET", f"/project/v1/projects/{pid}/member-groups/{member_group_id}",
            ))
        except Exception as e:
            return err(e)

    # ── 템플릿 ─────────────────────────────────────────────

    @mcp.tool()
    def dooray_template_create(project_id: str, body_json: str) -> str:
        """업무 템플릿을 생성합니다. (POST /project/v1/projects/{id}/templates)

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            body_json: 템플릿 정의 JSON. 예:
                '{"templateName": "장애보고", "subject": "[장애] ", "body": {"mimeType": "text/x-markdown", "content": "## 현상\\n"}}'
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            payload = parse_json(body_json, "body_json", dict)
            if not payload:
                raise ValidationError("body_json이 비어있습니다.")
            return ok(client.api(
                "POST", f"/project/v1/projects/{pid}/templates", payload=payload,
            ))
        except Exception as e:
            logger.error(f"template_create 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_template_get(
        project_id: str,
        template_id: str,
        interpolation: bool = False,
    ) -> str:
        """업무 템플릿 상세를 조회합니다. (GET /project/v1/projects/{id}/templates/{template-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            template_id: 템플릿 ID (필수)
            interpolation: 치환 변수를 실제 값으로 변환할지 여부
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            params = {"interpolation": "true"} if interpolation else None
            return ok(client.api(
                "GET", f"/project/v1/projects/{pid}/templates/{template_id}",
                params=params,
            ))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_template_update(project_id: str, template_id: str, body_json: str) -> str:
        """업무 템플릿을 수정합니다. (PUT /project/v1/projects/{id}/templates/{template-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            template_id: 템플릿 ID (필수)
            body_json: 수정할 템플릿 정의 JSON
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            payload = parse_json(body_json, "body_json", dict)
            if not payload:
                raise ValidationError("body_json이 비어있습니다.")
            client.api(
                "PUT", f"/project/v1/projects/{pid}/templates/{template_id}",
                payload=payload,
            )
            return ok({"message": f"템플릿 수정 완료: {template_id}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_template_delete(
        project_id: str,
        template_id: str,
        confirm: bool = False,
    ) -> str:
        """업무 템플릿을 삭제합니다. (DELETE /project/v1/projects/{id}/templates/{template-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            template_id: 삭제할 템플릿 ID (필수)
            confirm: 삭제 확인 (true여야 실제 삭제)
        """
        try:
            if not confirm:
                return need_confirm("템플릿 삭제", template_id)
            client = get_client()
            pid = client._resolve_project(project_id)
            client.api("DELETE", f"/project/v1/projects/{pid}/templates/{template_id}")
            return ok({"message": f"템플릿 삭제 완료: {template_id}"})
        except Exception as e:
            return err(e)
