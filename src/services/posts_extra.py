"""Project > Posts 확장 API — 전역 조회, 초안, 상태 변경, 파일/로그 관리

엔드포인트:
- GET  /project/v1/posts/{post-id}
- POST /project/v1/post-drafts
- POST /project/v1/post-drafts/{post-draft-id}/files
- PUT  /project/v1/projects/{id}/posts/{post-id}/to/{organization-member-id}
- POST /project/v1/projects/{id}/posts/{post-id}/set-workflow
- POST /project/v1/projects/{id}/posts/{post-id}/set-done
- POST /project/v1/projects/{id}/posts/{post-id}/set-parent-post
- GET  /project/v1/projects/{id}/posts/{post-id}/files/{file-id}?media=meta
- DELETE /project/v1/projects/{id}/posts/{post-id}/files/{file-id}
- GET/PUT/DELETE /project/v1/projects/{id}/posts/{post-id}/logs/{log-id}
"""

from __future__ import annotations

from ..validators import ValidationError, validate_post_id
from ._base import err, logger, markdown_body, need_confirm, ok, parse_json


def register(mcp, get_client):

    @mcp.tool()
    def dooray_post_get_global(post_id: str) -> str:
        """프로젝트 ID 없이 업무를 전역 조회합니다. (GET /project/v1/posts/{post-id})

        어느 프로젝트 소속인지 모르는 업무 ID로 상세 정보를 조회할 때 사용합니다.

        Args:
            post_id: 업무 ID (필수)
        """
        try:
            post_id = validate_post_id(post_id)
            return ok(get_client().api("GET", f"/project/v1/posts/{post_id}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_post_draft_create(body_json: str) -> str:
        """업무 초안(draft)을 생성합니다. (POST /project/v1/post-drafts)

        Args:
            body_json: 초안 정의 JSON. 예:
                '{"projectId": "123", "subject": "제목", "body": {"mimeType": "text/x-markdown", "content": "본문"}}'
        """
        try:
            payload = parse_json(body_json, "body_json", dict)
            if not payload:
                raise ValidationError("body_json이 비어있습니다.")
            return ok(get_client().api("POST", "/project/v1/post-drafts", payload=payload))
        except Exception as e:
            logger.error(f"post_draft_create 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_post_draft_upload_file(post_draft_id: str, file_path: str) -> str:
        """업무 초안에 파일을 첨부합니다. (POST /project/v1/post-drafts/{post-draft-id}/files)

        Args:
            post_draft_id: 초안 ID (필수)
            file_path: 업로드할 로컬 파일 경로 (필수)
        """
        try:
            result = get_client().api_upload(
                f"/project/v1/post-drafts/{post_draft_id}/files", file_path,
            )
            return ok({"message": "초안 파일 첨부 완료", "result": result})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_post_set_member_workflow(
        project_id: str,
        post_id: str,
        organization_member_id: str,
        workflow_id: str,
    ) -> str:
        """담당자별 업무 처리 상태를 변경합니다. (PUT .../posts/{post-id}/to/{organization-member-id})

        담당자가 여러 명일 때 특정 담당자의 상태만 변경합니다.

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            post_id: 업무 ID (필수)
            organization_member_id: 담당자의 조직 멤버 ID (필수)
            workflow_id: 변경할 워크플로우 ID (필수)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            post_id = validate_post_id(post_id)
            client.api(
                "PUT",
                f"/project/v1/projects/{pid}/posts/{post_id}/to/{organization_member_id}",
                payload={"workflowId": workflow_id},
            )
            return ok({"message": f"담당자({organization_member_id}) 상태 변경 완료 → {workflow_id}"})
        except Exception as e:
            logger.error(f"post_set_member_workflow 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_post_set_workflow(project_id: str, post_id: str, workflow_id: str) -> str:
        """업무 전체의 상태(워크플로우)를 변경합니다. (POST .../posts/{post-id}/set-workflow)

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            post_id: 업무 ID (필수)
            workflow_id: 변경할 워크플로우 ID (필수, dooray_list_workflows로 확인)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            post_id = validate_post_id(post_id)
            client.api(
                "POST", f"/project/v1/projects/{pid}/posts/{post_id}/set-workflow",
                payload={"workflowId": workflow_id},
            )
            return ok({
                "message": f"업무 상태 변경 완료 → {workflow_id}",
                "link": client.task_link(post_id),
            })
        except Exception as e:
            logger.error(f"post_set_workflow 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_post_set_done(project_id: str, post_id: str) -> str:
        """업무를 완료 상태로 변경합니다. (POST .../posts/{post-id}/set-done)

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            post_id: 업무 ID (필수)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            post_id = validate_post_id(post_id)
            client.api(
                "POST", f"/project/v1/projects/{pid}/posts/{post_id}/set-done",
                payload={},
            )
            return ok({"message": "업무 완료 처리됨", "link": client.task_link(post_id)})
        except Exception as e:
            logger.error(f"post_set_done 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_post_set_parent(project_id: str, post_id: str, parent_post_id: str) -> str:
        """업무의 상위 업무를 지정합니다. (POST .../posts/{post-id}/set-parent-post)

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            post_id: 업무 ID (필수)
            parent_post_id: 상위 업무 ID (필수)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            post_id = validate_post_id(post_id)
            parent_post_id = validate_post_id(parent_post_id, "parent_post_id")
            client.api(
                "POST", f"/project/v1/projects/{pid}/posts/{post_id}/set-parent-post",
                payload={"parentPostId": parent_post_id},
            )
            return ok({"message": f"상위 업무 지정 완료 → {parent_post_id}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_post_file_meta(project_id: str, post_id: str, file_id: str) -> str:
        """업무 첨부파일의 메타 정보를 조회합니다. (GET .../files/{file-id}?media=meta)

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            post_id: 업무 ID (필수)
            file_id: 파일 ID (필수)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            post_id = validate_post_id(post_id)
            return ok(client.api(
                "GET", f"/project/v1/projects/{pid}/posts/{post_id}/files/{file_id}",
                params={"media": "meta"},
            ))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_post_file_delete(
        project_id: str,
        post_id: str,
        file_id: str,
        confirm: bool = False,
    ) -> str:
        """업무 첨부파일을 삭제합니다. (DELETE .../posts/{post-id}/files/{file-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            post_id: 업무 ID (필수)
            file_id: 삭제할 파일 ID (필수)
            confirm: 삭제 확인 (true여야 실제 삭제)
        """
        try:
            if not confirm:
                return need_confirm("첨부파일 삭제", file_id)
            client = get_client()
            pid = client._resolve_project(project_id)
            post_id = validate_post_id(post_id)
            client.api(
                "DELETE", f"/project/v1/projects/{pid}/posts/{post_id}/files/{file_id}",
            )
            return ok({"message": f"첨부파일 삭제 완료: {file_id}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_post_log_get(project_id: str, post_id: str, log_id: str) -> str:
        """업무 댓글(로그) 1개를 조회합니다. (GET .../posts/{post-id}/logs/{log-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            post_id: 업무 ID (필수)
            log_id: 댓글(로그) ID (필수)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            post_id = validate_post_id(post_id)
            return ok(client.api(
                "GET", f"/project/v1/projects/{pid}/posts/{post_id}/logs/{log_id}",
            ))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_post_log_update(
        project_id: str,
        post_id: str,
        log_id: str,
        content_md: str,
    ) -> str:
        """업무 댓글(로그)을 수정합니다. (PUT .../posts/{post-id}/logs/{log-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            post_id: 업무 ID (필수)
            log_id: 댓글(로그) ID (필수)
            content_md: 새 댓글 내용 (마크다운, 필수)
        """
        try:
            client = get_client()
            pid = client._resolve_project(project_id)
            post_id = validate_post_id(post_id)
            client.api(
                "PUT", f"/project/v1/projects/{pid}/posts/{post_id}/logs/{log_id}",
                payload={"body": markdown_body(content_md)},
            )
            return ok({"message": f"댓글 수정 완료: {log_id}"})
        except Exception as e:
            logger.error(f"post_log_update 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_post_log_delete(
        project_id: str,
        post_id: str,
        log_id: str,
        confirm: bool = False,
    ) -> str:
        """업무 댓글(로그)을 삭제합니다. (DELETE .../posts/{post-id}/logs/{log-id})

        Args:
            project_id: 프로젝트 ID 또는 별칭 (필수)
            post_id: 업무 ID (필수)
            log_id: 삭제할 댓글(로그) ID (필수)
            confirm: 삭제 확인 (true여야 실제 삭제)
        """
        try:
            if not confirm:
                return need_confirm("댓글 삭제", log_id)
            client = get_client()
            pid = client._resolve_project(project_id)
            post_id = validate_post_id(post_id)
            client.api(
                "DELETE", f"/project/v1/projects/{pid}/posts/{post_id}/logs/{log_id}",
            )
            return ok({"message": f"댓글 삭제 완료: {log_id}"})
        except Exception as e:
            return err(e)
