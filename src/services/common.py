"""Common API — 멤버, Incoming Hook, Streams + 범용 API 호출

엔드포인트:
- GET    /common/v1/members
- GET    /common/v1/members/{member-id}
- GET    /common/v1/members/me
- POST   /common/v1/incoming-hooks
- GET    /common/v1/incoming-hooks/{incoming-hook-id}
- DELETE /common/v1/incoming-hooks/{incoming-hook-id}
- GET    /common/v1/streams
"""

from __future__ import annotations

from ..validators import ValidationError
from ._base import err, logger, need_confirm, ok, parse_json


def register(mcp, get_client):

    @mcp.tool()
    def dooray_common_list_members(
        name: str = "",
        external_emails: str = "",
        user_code: str = "",
        id_provider_user_id: str = "",
        page: int = 0,
        size: int = 100,
    ) -> str:
        """조직 전체 멤버를 검색합니다. (GET /common/v1/members)

        Args:
            name: 이름 검색
            external_emails: 이메일 주소 (쉼표 구분)
            user_code: 사용자 코드(아이디)
            id_provider_user_id: ID Provider 사용자 ID
            page: 페이지 번호 (0부터)
            size: 페이지 크기
        """
        try:
            params = {"page": page, "size": size}
            if name:
                params["name"] = name
            if external_emails:
                params["externalEmailAddresses"] = external_emails
            if user_code:
                params["userCode"] = user_code
            if id_provider_user_id:
                params["idProviderUserId"] = id_provider_user_id
            result = get_client().api("GET", "/common/v1/members", params=params, full=True)
            return ok({"members": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            logger.error(f"common_list_members 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_common_get_member(member_id: str) -> str:
        """조직 멤버 1명의 상세 정보를 조회합니다. (GET /common/v1/members/{member-id})

        Args:
            member_id: 조직 멤버 ID (필수)
        """
        try:
            return ok(get_client().api("GET", f"/common/v1/members/{member_id}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_common_me() -> str:
        """현재 API 토큰 소유자(나)의 멤버 정보를 조회합니다. (GET /common/v1/members/me)"""
        try:
            return ok(get_client().api("GET", "/common/v1/members/me"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_common_create_incoming_hook(
        name: str,
        body_json: str = "",
    ) -> str:
        """Incoming Hook(웹훅 수신 URL)을 생성합니다. (POST /common/v1/incoming-hooks)

        Args:
            name: 훅 이름 (필수)
            body_json: 추가 바디 필드 JSON (예: '{"description": "알림용"}')
        """
        try:
            payload = {"name": name}
            extra = parse_json(body_json, "body_json", dict)
            if extra:
                payload.update(extra)
            return ok(get_client().api("POST", "/common/v1/incoming-hooks", payload=payload))
        except Exception as e:
            logger.error(f"common_create_incoming_hook 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_common_get_incoming_hook(incoming_hook_id: str) -> str:
        """Incoming Hook 정보를 조회합니다. (GET /common/v1/incoming-hooks/{id})

        Args:
            incoming_hook_id: Incoming Hook ID (필수)
        """
        try:
            return ok(get_client().api("GET", f"/common/v1/incoming-hooks/{incoming_hook_id}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_common_delete_incoming_hook(
        incoming_hook_id: str,
        confirm: bool = False,
    ) -> str:
        """Incoming Hook을 삭제합니다. (DELETE /common/v1/incoming-hooks/{id})

        Args:
            incoming_hook_id: Incoming Hook ID (필수)
            confirm: 삭제 확인 (true여야 실제 삭제)
        """
        try:
            if not confirm:
                return need_confirm("Incoming Hook 삭제", incoming_hook_id)
            get_client().api("DELETE", f"/common/v1/incoming-hooks/{incoming_hook_id}")
            return ok({"message": f"Incoming Hook 삭제 완료: {incoming_hook_id}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_common_list_streams(
        page: int = 0,
        size: int = 20,
        params_json: str = "",
    ) -> str:
        """내 스트림(알림 피드)을 조회합니다. (GET /common/v1/streams)

        Args:
            page: 페이지 번호 (0부터)
            size: 페이지 크기
            params_json: 추가 쿼리 파라미터 JSON (예: '{"from": "2026-07-01T00:00:00+09:00"}')
        """
        try:
            params = {"page": page, "size": size}
            extra = parse_json(params_json, "params_json", dict)
            if extra:
                params.update(extra)
            result = get_client().api("GET", "/common/v1/streams", params=params, full=True)
            return ok({"streams": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_api_call(
        method: str,
        path: str,
        params_json: str = "",
        body_json: str = "",
    ) -> str:
        """Dooray API를 직접 호출합니다 (범용 escape hatch).

        전용 툴이 없는 엔드포인트나 문서의 추가 파라미터가 필요할 때 사용하세요.
        예: dooray_api_call("GET", "/project/v1/projects", params_json='{"member": "me", "size": 100}')

        Args:
            method: GET / POST / PUT / DELETE
            path: API 경로 (예: "/wiki/v1/wikis")
            params_json: 쿼리 파라미터 JSON 객체
            body_json: 요청 바디 JSON (객체 또는 배열)
        """
        try:
            params = parse_json(params_json, "params_json", dict)
            payload = parse_json(body_json, "body_json")
            result = get_client().api(method, path, params=params, payload=payload, full=True)
            return ok(result)
        except Exception as e:
            logger.error(f"api_call 실패: {e}")
            return err(e)
