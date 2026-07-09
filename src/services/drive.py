"""Drive API — 드라이브 및 파일 관리

엔드포인트:
- GET /drive/v1/drives, GET /drive/v1/drives/{drive-id}
- GET /drive/v2/drives/{drive-id}/changes
- GET /drive/v1/files/{file-id}?media=meta
- POST /drive/v1/drives/{drive-id}/files?parentId={}
- GET /drive/v1/drives/{drive-id}/files (+ 단건 meta/raw)
- PUT meta/raw, DELETE
- POST create-folder / copy / move
- SharedLinks: POST/GET/GET/PUT/DELETE
"""

from __future__ import annotations

from ..validators import ValidationError
from ._base import err, logger, need_confirm, ok, parse_json


def register(mcp, get_client):

    @mcp.tool()
    def dooray_drive_list(drive_type: str = "private", params_json: str = "") -> str:
        """접근 가능한 드라이브 목록을 조회합니다. (GET /drive/v1/drives)

        Args:
            drive_type: 드라이브 종류 (private=개인 | public=프로젝트 공용)
            params_json: 추가 쿼리 파라미터 JSON (예: '{"projectCode": "my-project"}')
        """
        try:
            params = {"type": drive_type}
            extra = parse_json(params_json, "params_json", dict)
            if extra:
                params.update(extra)
            result = get_client().api("GET", "/drive/v1/drives", params=params, full=True)
            return ok({"drives": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_drive_get(drive_id: str) -> str:
        """드라이브 상세 정보를 조회합니다. (GET /drive/v1/drives/{drive-id})

        Args:
            drive_id: 드라이브 ID (필수)
        """
        try:
            return ok(get_client().api("GET", f"/drive/v1/drives/{drive_id}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_drive_changes(drive_id: str, params_json: str = "") -> str:
        """드라이브 변경 사항 목록을 조회합니다. (GET /drive/v2/drives/{drive-id}/changes)

        Args:
            drive_id: 드라이브 ID (필수)
            params_json: 쿼리 파라미터 JSON (예: '{"pageToken": "...", "limit": 100}')
        """
        try:
            params = parse_json(params_json, "params_json", dict)
            result = get_client().api(
                "GET", f"/drive/v2/drives/{drive_id}/changes", params=params, full=True,
            )
            return ok({"changes": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_drive_file_meta_global(file_id: str) -> str:
        """드라이브 ID 없이 파일 메타 정보를 조회합니다. (GET /drive/v1/files/{file-id}?media=meta)

        Args:
            file_id: 파일 ID (필수)
        """
        try:
            return ok(get_client().api(
                "GET", f"/drive/v1/files/{file_id}", params={"media": "meta"},
            ))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_drive_upload(drive_id: str, parent_id: str, file_path: str) -> str:
        """드라이브에 파일을 업로드합니다. (POST /drive/v1/drives/{drive-id}/files?parentId={})

        Args:
            drive_id: 드라이브 ID (필수)
            parent_id: 업로드할 상위 폴더 ID (필수, 루트는 드라이브의 rootFolderId)
            file_path: 업로드할 로컬 파일 경로 (필수)
        """
        try:
            result = get_client().api_upload(
                f"/drive/v1/drives/{drive_id}/files", file_path,
                params={"parentId": parent_id},
            )
            return ok({"message": "드라이브 업로드 완료", "result": result})
        except Exception as e:
            logger.error(f"drive_upload 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_drive_list_files(
        drive_id: str,
        parent_id: str = "",
        file_type: str = "",
        page: int = 0,
        size: int = 100,
    ) -> str:
        """드라이브 파일/폴더 목록을 조회합니다. (GET /drive/v1/drives/{drive-id}/files)

        Args:
            drive_id: 드라이브 ID (필수)
            parent_id: 상위 폴더 ID (미지정 시 루트)
            file_type: 필터 (file | folder)
            page: 페이지 번호
            size: 페이지 크기
        """
        try:
            params = {"page": page, "size": size}
            if parent_id:
                params["parentId"] = parent_id
            if file_type:
                params["type"] = file_type
            result = get_client().api(
                "GET", f"/drive/v1/drives/{drive_id}/files", params=params, full=True,
            )
            return ok({"files": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_drive_file_meta(drive_id: str, file_id: str) -> str:
        """드라이브 파일 메타 정보를 조회합니다. (GET .../files/{file-id}?media=meta)

        Args:
            drive_id: 드라이브 ID (필수)
            file_id: 파일 ID (필수)
        """
        try:
            return ok(get_client().api(
                "GET", f"/drive/v1/drives/{drive_id}/files/{file_id}",
                params={"media": "meta"},
            ))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_drive_download(drive_id: str, file_id: str, file_name: str) -> str:
        """드라이브 파일을 로컬에 다운로드합니다. (GET .../files/{file-id}?media=raw)

        Args:
            drive_id: 드라이브 ID (필수)
            file_id: 파일 ID (필수)
            file_name: 저장할 파일명 (필수)
        """
        try:
            local_path = get_client().api_download(
                f"/drive/v1/drives/{drive_id}/files/{file_id}",
                file_name, params={"media": "raw"},
            )
            return ok({"로컬경로": local_path, "message": f"다운로드 완료: {file_name}"})
        except Exception as e:
            logger.error(f"drive_download 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_drive_update_file_meta(drive_id: str, file_id: str, body_json: str) -> str:
        """드라이브 파일 메타(이름 등)를 수정합니다. (PUT .../files/{file-id}?media=meta)

        Args:
            drive_id: 드라이브 ID (필수)
            file_id: 파일 ID (필수)
            body_json: 수정 바디 JSON (예: '{"name": "새이름.pdf"}')
        """
        try:
            payload = parse_json(body_json, "body_json", dict)
            if not payload:
                raise ValidationError("body_json이 비어있습니다.")
            get_client().api(
                "PUT", f"/drive/v1/drives/{drive_id}/files/{file_id}",
                params={"media": "meta"}, payload=payload,
            )
            return ok({"message": f"파일 메타 수정 완료: {file_id}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_drive_update_file_content(drive_id: str, file_id: str, file_path: str) -> str:
        """드라이브 파일 내용을 새 파일로 교체합니다. (PUT .../files/{file-id}?media=raw)

        Args:
            drive_id: 드라이브 ID (필수)
            file_id: 파일 ID (필수)
            file_path: 교체할 로컬 파일 경로 (필수)
        """
        try:
            import os as _os
            import requests as _requests

            client = get_client()
            if not _os.path.isfile(file_path):
                raise ValidationError(f"파일을 찾을 수 없습니다: {file_path}")
            url = f"{client.API_ORIGIN}/drive/v1/drives/{drive_id}/files/{file_id}"
            client._rate_limit()
            with open(file_path, "rb") as f:
                resp = _requests.put(
                    url,
                    headers={"Authorization": f"dooray-api {client.api_token}"},
                    params={"media": "raw"},
                    files={"file": (_os.path.basename(file_path), f)},
                    timeout=120,
                )
            if resp.status_code not in (200, 201):
                raise ValidationError(f"[파일 교체] HTTP {resp.status_code}: {resp.text[:300]}")
            return ok({"message": f"파일 내용 교체 완료: {file_id}"})
        except Exception as e:
            logger.error(f"drive_update_file_content 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_drive_delete_file(drive_id: str, file_id: str, confirm: bool = False) -> str:
        """드라이브 파일/폴더를 삭제합니다. (DELETE /drive/v1/drives/{drive-id}/files/{file-id})

        Args:
            drive_id: 드라이브 ID (필수)
            file_id: 삭제할 파일/폴더 ID (필수)
            confirm: 삭제 확인 (true여야 실제 삭제)
        """
        try:
            if not confirm:
                return need_confirm("드라이브 파일 삭제", file_id)
            get_client().api("DELETE", f"/drive/v1/drives/{drive_id}/files/{file_id}")
            return ok({"message": f"파일 삭제 완료: {file_id}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_drive_create_folder(drive_id: str, parent_folder_id: str, name: str) -> str:
        """드라이브에 폴더를 생성합니다. (POST .../files/{folder-id}/create-folder)

        Args:
            drive_id: 드라이브 ID (필수)
            parent_folder_id: 상위 폴더 ID (필수, 루트는 드라이브의 rootFolderId)
            name: 새 폴더 이름 (필수)
        """
        try:
            return ok(get_client().api(
                "POST",
                f"/drive/v1/drives/{drive_id}/files/{parent_folder_id}/create-folder",
                payload={"name": name},
            ))
        except Exception as e:
            logger.error(f"drive_create_folder 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_drive_copy_file(drive_id: str, file_id: str, body_json: str) -> str:
        """드라이브 파일을 복사합니다. (POST .../files/{file-id}/copy)

        Args:
            drive_id: 원본 드라이브 ID (필수)
            file_id: 복사할 파일 ID (필수)
            body_json: 대상 정의 JSON (예: '{"destination": {"driveId": "123", "parentId": "456"}}')
        """
        try:
            payload = parse_json(body_json, "body_json", dict)
            if not payload:
                raise ValidationError("body_json이 비어있습니다.")
            return ok(get_client().api(
                "POST", f"/drive/v1/drives/{drive_id}/files/{file_id}/copy",
                payload=payload,
            ))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_drive_move_file(drive_id: str, file_id: str, body_json: str) -> str:
        """드라이브 파일을 이동합니다. (POST .../files/{file-id}/move)

        Args:
            drive_id: 원본 드라이브 ID (필수)
            file_id: 이동할 파일 ID (필수)
            body_json: 대상 정의 JSON (예: '{"destination": {"driveId": "123", "parentId": "456"}}')
        """
        try:
            payload = parse_json(body_json, "body_json", dict)
            if not payload:
                raise ValidationError("body_json이 비어있습니다.")
            return ok(get_client().api(
                "POST", f"/drive/v1/drives/{drive_id}/files/{file_id}/move",
                payload=payload,
            ))
        except Exception as e:
            return err(e)

    # ── 공유 링크 ──────────────────────────────────────────

    @mcp.tool()
    def dooray_drive_shared_link_create(
        drive_id: str,
        file_id: str,
        scope: str = "member",
        expired_at: str = "",
        body_json: str = "",
    ) -> str:
        """드라이브 파일 공유 링크를 생성합니다. (POST .../files/{file-id}/shared-links)

        Args:
            drive_id: 드라이브 ID (필수)
            file_id: 파일 ID (필수)
            scope: 공유 범위 (member | memberAndGuest | all)
            expired_at: 만료 시각 (ISO 형식, 예: "2026-08-01T00:00:00+09:00")
            body_json: 추가 바디 필드 JSON
        """
        try:
            payload = {"scope": scope}
            if expired_at:
                payload["expiredAt"] = expired_at
            extra = parse_json(body_json, "body_json", dict)
            if extra:
                payload.update(extra)
            return ok(get_client().api(
                "POST", f"/drive/v1/drives/{drive_id}/files/{file_id}/shared-links",
                payload=payload,
            ))
        except Exception as e:
            logger.error(f"drive_shared_link_create 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_drive_shared_links(drive_id: str, file_id: str) -> str:
        """드라이브 파일의 공유 링크 목록을 조회합니다. (GET .../files/{file-id}/shared-links)

        Args:
            drive_id: 드라이브 ID (필수)
            file_id: 파일 ID (필수)
        """
        try:
            result = get_client().api(
                "GET", f"/drive/v1/drives/{drive_id}/files/{file_id}/shared-links",
                full=True,
            )
            return ok({"sharedLinks": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_drive_shared_link_get(drive_id: str, file_id: str, link_id: str) -> str:
        """공유 링크 상세 정보를 조회합니다. (GET .../shared-links/{link-id})

        Args:
            drive_id: 드라이브 ID (필수)
            file_id: 파일 ID (필수)
            link_id: 공유 링크 ID (필수)
        """
        try:
            return ok(get_client().api(
                "GET",
                f"/drive/v1/drives/{drive_id}/files/{file_id}/shared-links/{link_id}",
            ))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_drive_shared_link_update(
        drive_id: str,
        file_id: str,
        link_id: str,
        body_json: str,
    ) -> str:
        """공유 링크를 수정합니다. (PUT .../shared-links/{link-id})

        Args:
            drive_id: 드라이브 ID (필수)
            file_id: 파일 ID (필수)
            link_id: 공유 링크 ID (필수)
            body_json: 수정 바디 JSON (예: '{"scope": "all", "expiredAt": "2026-12-31T00:00:00+09:00"}')
        """
        try:
            payload = parse_json(body_json, "body_json", dict)
            if not payload:
                raise ValidationError("body_json이 비어있습니다.")
            get_client().api(
                "PUT",
                f"/drive/v1/drives/{drive_id}/files/{file_id}/shared-links/{link_id}",
                payload=payload,
            )
            return ok({"message": f"공유 링크 수정 완료: {link_id}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_drive_shared_link_delete(
        drive_id: str,
        file_id: str,
        link_id: str,
        confirm: bool = False,
    ) -> str:
        """공유 링크를 삭제합니다. (DELETE .../shared-links/{link-id})

        Args:
            drive_id: 드라이브 ID (필수)
            file_id: 파일 ID (필수)
            link_id: 삭제할 공유 링크 ID (필수)
            confirm: 삭제 확인 (true여야 실제 삭제)
        """
        try:
            if not confirm:
                return need_confirm("공유 링크 삭제", link_id)
            get_client().api(
                "DELETE",
                f"/drive/v1/drives/{drive_id}/files/{file_id}/shared-links/{link_id}",
            )
            return ok({"message": f"공유 링크 삭제 완료: {link_id}"})
        except Exception as e:
            return err(e)
