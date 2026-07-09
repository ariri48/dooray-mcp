"""Wiki API — 위키 페이지, 댓글, 첨부파일 관리

엔드포인트:
- GET /wiki/v1/wikis
- GET /wiki/v1/pages/{page-id}
- POST/GET /wiki/v1/wikis/{wiki-id}/pages (+ 단건 GET/PUT)
- PUT title / content / referrers, POST move, DELETE
- Comments: POST/GET/GET/PUT/DELETE
- SharedLinks: GET
- AttachFiles: GET (다운로드)
- Page Files: POST/GET/DELETE, Wiki Files: POST
"""

from __future__ import annotations

from ..validators import ValidationError
from ._base import (
    err, logger, markdown_body, member_refs, need_confirm, ok, parse_json, split_ids,
)


def register(mcp, get_client):

    @mcp.tool()
    def dooray_wiki_list(page: int = 0, size: int = 100) -> str:
        """접근 가능한 위키 목록을 조회합니다. (GET /wiki/v1/wikis)

        Args:
            page: 페이지 번호
            size: 페이지 크기
        """
        try:
            result = get_client().api(
                "GET", "/wiki/v1/wikis", params={"page": page, "size": size}, full=True,
            )
            return ok({"wikis": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_wiki_page_get_global(page_id: str) -> str:
        """위키 ID 없이 페이지를 전역 조회합니다. (GET /wiki/v1/pages/{page-id})

        Args:
            page_id: 위키 페이지 ID (필수)
        """
        try:
            return ok(get_client().api("GET", f"/wiki/v1/pages/{page_id}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_wiki_page_create(
        wiki_id: str,
        subject: str,
        content_md: str,
        parent_page_id: str = "",
        referrer_ids: str = "",
        attach_file_ids: str = "",
    ) -> str:
        """위키 페이지를 생성합니다. (POST /wiki/v1/wikis/{wiki-id}/pages)

        Args:
            wiki_id: 위키 ID (필수, dooray_wiki_list로 확인)
            subject: 페이지 제목 (필수)
            content_md: 페이지 내용 (마크다운, 필수)
            parent_page_id: 상위 페이지 ID (미지정 시 루트)
            referrer_ids: 참조자 조직 멤버 ID (쉼표 구분)
            attach_file_ids: 첨부할 파일 ID (쉼표 구분, dooray_wiki_file_upload 결과)
        """
        try:
            payload = {
                "subject": subject,
                "body": markdown_body(content_md),
            }
            if parent_page_id:
                payload["parentPageId"] = parent_page_id
            refs = split_ids(referrer_ids)
            if refs:
                payload["referrers"] = member_refs(refs)
            files = split_ids(attach_file_ids)
            if files:
                payload["attachFileIds"] = files
            return ok(get_client().api(
                "POST", f"/wiki/v1/wikis/{wiki_id}/pages", payload=payload,
            ))
        except Exception as e:
            logger.error(f"wiki_page_create 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_wiki_pages(wiki_id: str, parent_page_id: str = "") -> str:
        """위키 페이지 목록을 조회합니다. (GET /wiki/v1/wikis/{wiki-id}/pages)

        Args:
            wiki_id: 위키 ID (필수)
            parent_page_id: 상위 페이지 ID (지정 시 해당 페이지의 하위 목록)
        """
        try:
            params = {"parentPageId": parent_page_id} if parent_page_id else None
            result = get_client().api(
                "GET", f"/wiki/v1/wikis/{wiki_id}/pages", params=params, full=True,
            )
            return ok({"pages": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_wiki_page_get(wiki_id: str, page_id: str) -> str:
        """위키 페이지 상세(본문 포함)를 조회합니다. (GET /wiki/v1/wikis/{wiki-id}/pages/{page-id})

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 페이지 ID (필수)
        """
        try:
            return ok(get_client().api("GET", f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_wiki_page_update(
        wiki_id: str,
        page_id: str,
        subject: str = "",
        content_md: str = "",
        referrer_ids: str = "",
    ) -> str:
        """위키 페이지를 수정합니다. 변경할 필드만 입력하세요. (PUT /wiki/v1/wikis/{wiki-id}/pages/{page-id})

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 페이지 ID (필수)
            subject: 새 제목
            content_md: 새 내용 (마크다운)
            referrer_ids: 새 참조자 조직 멤버 ID (쉼표 구분)
        """
        try:
            payload = {}
            if subject:
                payload["subject"] = subject
            if content_md:
                payload["body"] = markdown_body(content_md)
            refs = split_ids(referrer_ids)
            if refs:
                payload["referrers"] = member_refs(refs)
            if not payload:
                raise ValidationError("변경할 내용이 없습니다.")
            get_client().api(
                "PUT", f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}", payload=payload,
            )
            return ok({"message": f"위키 페이지 수정 완료: {page_id}", "변경": list(payload.keys())})
        except Exception as e:
            logger.error(f"wiki_page_update 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_wiki_page_update_title(wiki_id: str, page_id: str, subject: str) -> str:
        """위키 페이지 제목만 변경합니다. (PUT .../pages/{page-id}/title)

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 페이지 ID (필수)
            subject: 새 제목 (필수)
        """
        try:
            get_client().api(
                "PUT", f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/title",
                payload={"subject": subject},
            )
            return ok({"message": f"제목 변경 완료 → {subject}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_wiki_page_update_content(wiki_id: str, page_id: str, content_md: str) -> str:
        """위키 페이지 본문만 변경합니다. (PUT .../pages/{page-id}/content)

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 페이지 ID (필수)
            content_md: 새 본문 (마크다운, 필수)
        """
        try:
            get_client().api(
                "PUT", f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/content",
                payload={"body": markdown_body(content_md)},
            )
            return ok({"message": f"본문 변경 완료: {page_id}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_wiki_page_update_referrers(wiki_id: str, page_id: str, referrer_ids: str) -> str:
        """위키 페이지 참조자를 변경합니다. (PUT .../pages/{page-id}/referrers)

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 페이지 ID (필수)
            referrer_ids: 참조자 조직 멤버 ID (쉼표 구분, 필수)
        """
        try:
            refs = split_ids(referrer_ids)
            if not refs:
                raise ValidationError("referrer_ids가 비어있습니다.")
            get_client().api(
                "PUT", f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/referrers",
                payload={"referrers": member_refs(refs)},
            )
            return ok({"message": f"참조자 변경 완료: {len(refs)}명"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_wiki_page_move(wiki_id: str, page_id: str, parent_page_id: str) -> str:
        """위키 페이지를 다른 상위 페이지 아래로 이동합니다. (POST .../pages/{page-id}/move)

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 이동할 페이지 ID (필수)
            parent_page_id: 새 상위 페이지 ID (필수)
        """
        try:
            get_client().api(
                "POST", f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/move",
                payload={"parentPageId": parent_page_id},
            )
            return ok({"message": f"페이지 이동 완료 → 상위 {parent_page_id}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_wiki_page_delete(wiki_id: str, page_id: str, confirm: bool = False) -> str:
        """위키 페이지를 삭제합니다. (DELETE /wiki/v1/wikis/{wiki-id}/pages/{page-id})

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 삭제할 페이지 ID (필수)
            confirm: 삭제 확인 (true여야 실제 삭제)
        """
        try:
            if not confirm:
                return need_confirm("위키 페이지 삭제", page_id)
            get_client().api("DELETE", f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}")
            return ok({"message": f"위키 페이지 삭제 완료: {page_id}"})
        except Exception as e:
            return err(e)

    # ── 댓글 ───────────────────────────────────────────────

    @mcp.tool()
    def dooray_wiki_comment_create(wiki_id: str, page_id: str, content_md: str) -> str:
        """위키 페이지에 댓글을 작성합니다. (POST .../pages/{page-id}/comments)

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 페이지 ID (필수)
            content_md: 댓글 내용 (마크다운, 필수)
        """
        try:
            return ok(get_client().api(
                "POST", f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/comments",
                payload={"body": markdown_body(content_md)},
            ))
        except Exception as e:
            logger.error(f"wiki_comment_create 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_wiki_comments(wiki_id: str, page_id: str, page: int = 0, size: int = 100) -> str:
        """위키 페이지 댓글 목록을 조회합니다. (GET .../pages/{page-id}/comments)

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 페이지 ID (필수)
            page: 페이지 번호
            size: 페이지 크기
        """
        try:
            result = get_client().api(
                "GET", f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/comments",
                params={"page": page, "size": size}, full=True,
            )
            return ok({"comments": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_wiki_comment_get(wiki_id: str, page_id: str, comment_id: str) -> str:
        """위키 댓글 1개를 조회합니다. (GET .../comments/{comment-id})

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 페이지 ID (필수)
            comment_id: 댓글 ID (필수)
        """
        try:
            return ok(get_client().api(
                "GET", f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/comments/{comment_id}",
            ))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_wiki_comment_update(
        wiki_id: str,
        page_id: str,
        comment_id: str,
        content_md: str,
    ) -> str:
        """위키 댓글을 수정합니다. (PUT .../comments/{comment-id})

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 페이지 ID (필수)
            comment_id: 댓글 ID (필수)
            content_md: 새 댓글 내용 (마크다운, 필수)
        """
        try:
            get_client().api(
                "PUT", f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/comments/{comment_id}",
                payload={"body": markdown_body(content_md)},
            )
            return ok({"message": f"댓글 수정 완료: {comment_id}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_wiki_comment_delete(
        wiki_id: str,
        page_id: str,
        comment_id: str,
        confirm: bool = False,
    ) -> str:
        """위키 댓글을 삭제합니다. (DELETE .../comments/{comment-id})

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 페이지 ID (필수)
            comment_id: 삭제할 댓글 ID (필수)
            confirm: 삭제 확인 (true여야 실제 삭제)
        """
        try:
            if not confirm:
                return need_confirm("위키 댓글 삭제", comment_id)
            get_client().api(
                "DELETE",
                f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/comments/{comment_id}",
            )
            return ok({"message": f"댓글 삭제 완료: {comment_id}"})
        except Exception as e:
            return err(e)

    # ── 공유 링크 / 첨부파일 ──────────────────────────────

    @mcp.tool()
    def dooray_wiki_page_shared_links(wiki_id: str, page_id: str) -> str:
        """위키 페이지 공유 링크 목록을 조회합니다. (GET .../pages/{page-id}/shared-links)

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 페이지 ID (필수)
        """
        try:
            result = get_client().api(
                "GET", f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/shared-links", full=True,
            )
            return ok({"sharedLinks": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_wiki_attach_file_download(wiki_id: str, attach_file_id: str, file_name: str) -> str:
        """위키 첨부파일을 로컬에 다운로드합니다. (GET /wiki/v1/wikis/{wiki-id}/attachFiles/{attach-file-id})

        Args:
            wiki_id: 위키 ID (필수)
            attach_file_id: 첨부파일 ID (필수)
            file_name: 저장할 파일명 (필수)
        """
        try:
            local_path = get_client().api_download(
                f"/wiki/v1/wikis/{wiki_id}/attachFiles/{attach_file_id}", file_name,
            )
            return ok({"로컬경로": local_path, "message": f"다운로드 완료: {file_name}"})
        except Exception as e:
            logger.error(f"wiki_attach_file_download 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_wiki_page_file_upload(wiki_id: str, page_id: str, file_path: str) -> str:
        """위키 페이지에 파일을 첨부합니다. (POST .../pages/{page-id}/files)

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 페이지 ID (필수)
            file_path: 업로드할 로컬 파일 경로 (필수)
        """
        try:
            result = get_client().api_upload(
                f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/files", file_path,
            )
            return ok({"message": "위키 페이지 파일 첨부 완료", "result": result})
        except Exception as e:
            logger.error(f"wiki_page_file_upload 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_wiki_page_file_download(
        wiki_id: str,
        page_id: str,
        file_id: str,
        file_name: str,
    ) -> str:
        """위키 페이지 첨부파일을 로컬에 다운로드합니다. (GET .../pages/{page-id}/files/{file-id})

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 페이지 ID (필수)
            file_id: 파일 ID (필수)
            file_name: 저장할 파일명 (필수)
        """
        try:
            local_path = get_client().api_download(
                f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/files/{file_id}", file_name,
            )
            return ok({"로컬경로": local_path, "message": f"다운로드 완료: {file_name}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_wiki_page_file_delete(
        wiki_id: str,
        page_id: str,
        file_id: str,
        confirm: bool = False,
    ) -> str:
        """위키 페이지 첨부파일을 삭제합니다. (DELETE .../pages/{page-id}/files/{file-id})

        Args:
            wiki_id: 위키 ID (필수)
            page_id: 페이지 ID (필수)
            file_id: 삭제할 파일 ID (필수)
            confirm: 삭제 확인 (true여야 실제 삭제)
        """
        try:
            if not confirm:
                return need_confirm("위키 첨부파일 삭제", file_id)
            get_client().api(
                "DELETE", f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/files/{file_id}",
            )
            return ok({"message": f"첨부파일 삭제 완료: {file_id}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_wiki_file_upload(wiki_id: str, file_path: str) -> str:
        """위키에 파일을 업로드합니다 (페이지 생성 시 attach_file_ids로 사용). (POST /wiki/v1/wikis/{wiki-id}/files)

        Args:
            wiki_id: 위키 ID (필수)
            file_path: 업로드할 로컬 파일 경로 (필수)
        """
        try:
            result = get_client().api_upload(f"/wiki/v1/wikis/{wiki_id}/files", file_path)
            return ok({"message": "위키 파일 업로드 완료", "result": result})
        except Exception as e:
            logger.error(f"wiki_file_upload 실패: {e}")
            return err(e)
