"""Contact API — 주소록 관리

엔드포인트:
- GET  /contacts/v1/contacts
- GET  /contacts/v1/contacts/{contact-id}
- POST /contacts/v1/contacts/search
"""

from __future__ import annotations

from ..validators import ValidationError
from ._base import err, logger, ok, parse_json


def register(mcp, get_client):

    @mcp.tool()
    def dooray_contacts(page: int = 0, size: int = 100) -> str:
        """주소록 연락처 목록을 조회합니다. (GET /contacts/v1/contacts)

        Args:
            page: 페이지 번호
            size: 페이지 크기
        """
        try:
            result = get_client().api(
                "GET", "/contacts/v1/contacts",
                params={"page": page, "size": size}, full=True,
            )
            return ok({"contacts": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_contact_get(contact_id: str) -> str:
        """연락처 상세 정보를 조회합니다. (GET /contacts/v1/contacts/{contact-id})

        Args:
            contact_id: 연락처 ID (필수)
        """
        try:
            return ok(get_client().api("GET", f"/contacts/v1/contacts/{contact_id}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_contacts_search(
        keyword: str = "",
        body_json: str = "",
        page: int = 0,
        size: int = 100,
    ) -> str:
        """주소록에서 연락처를 검색합니다. (POST /contacts/v1/contacts/search)

        Args:
            keyword: 검색어 (이름/이메일 등)
            body_json: 검색 조건 바디 JSON (지정 시 keyword보다 우선, 문서의 검색 스펙 그대로 전달)
            page: 페이지 번호
            size: 페이지 크기
        """
        try:
            payload = parse_json(body_json, "body_json", dict)
            if payload is None:
                if not keyword.strip():
                    raise ValidationError("keyword 또는 body_json 중 하나는 필수입니다.")
                payload = {"keyword": keyword.strip()}
            result = get_client().api(
                "POST", "/contacts/v1/contacts/search",
                params={"page": page, "size": size}, payload=payload, full=True,
            )
            return ok({"contacts": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            logger.error(f"contacts_search 실패: {e}")
            return err(e)
