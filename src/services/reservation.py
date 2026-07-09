"""Reservation API — 자원(회의실 등) 예약 관리

엔드포인트:
- GET /reservation/v1/resource-categories
- GET /reservation/v1/resources, GET /reservation/v1/resources/{resource-id}
- GET /reservation/v1/reservable-resources
- GET/POST /reservation/v1/resource-reservations
- GET/PUT/DELETE /reservation/v1/resource-reservations/{id}
"""

from __future__ import annotations

from ..validators import ValidationError
from ._base import (
    err, logger, member_refs, need_confirm, ok, parse_json, split_ids,
)


def register(mcp, get_client):

    @mcp.tool()
    def dooray_resource_categories() -> str:
        """자원 카테고리 목록을 조회합니다. (GET /reservation/v1/resource-categories)"""
        try:
            result = get_client().api("GET", "/reservation/v1/resource-categories", full=True)
            return ok({"categories": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_resources(
        name: str = "",
        category_ids: str = "",
        page: int = 0,
        size: int = 100,
    ) -> str:
        """자원(회의실 등) 목록을 조회합니다. (GET /reservation/v1/resources)

        Args:
            name: 자원 이름 검색
            category_ids: 자원 카테고리 ID (쉼표 구분)
            page: 페이지 번호
            size: 페이지 크기
        """
        try:
            params = {"page": page, "size": size}
            if name:
                params["name"] = name
            if category_ids:
                params["resourceCategoryIds"] = category_ids
            result = get_client().api(
                "GET", "/reservation/v1/resources", params=params, full=True,
            )
            return ok({"resources": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_resource_get(resource_id: str) -> str:
        """자원 상세 정보를 조회합니다. (GET /reservation/v1/resources/{resource-id})

        Args:
            resource_id: 자원 ID (필수)
        """
        try:
            return ok(get_client().api("GET", f"/reservation/v1/resources/{resource_id}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_reservable_resources(
        time_min: str,
        time_max: str,
        category_id: str = "",
        params_json: str = "",
    ) -> str:
        """지정 시간대에 예약 가능한 자원을 조회합니다. (GET /reservation/v1/reservable-resources)

        Args:
            time_min: 시작 시각 (ISO 형식, 예: "2026-07-10T14:00:00+09:00")
            time_max: 종료 시각 (ISO 형식)
            category_id: 자원 카테고리 ID
            params_json: 추가 쿼리 파라미터 JSON
        """
        try:
            params = {"timeMin": time_min, "timeMax": time_max}
            if category_id:
                params["resourceCategoryId"] = category_id
            extra = parse_json(params_json, "params_json", dict)
            if extra:
                params.update(extra)
            result = get_client().api(
                "GET", "/reservation/v1/reservable-resources", params=params, full=True,
            )
            return ok({"resources": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_reservations(
        time_min: str,
        time_max: str,
        resource_ids: str = "",
        page: int = 0,
        size: int = 100,
    ) -> str:
        """자원 예약 목록을 조회합니다. (GET /reservation/v1/resource-reservations)

        Args:
            time_min: 조회 시작 시각 (ISO 형식)
            time_max: 조회 종료 시각 (ISO 형식)
            resource_ids: 자원 ID 필터 (쉼표 구분)
            page: 페이지 번호
            size: 페이지 크기
        """
        try:
            params = {"timeMin": time_min, "timeMax": time_max, "page": page, "size": size}
            if resource_ids:
                params["resourceIds"] = resource_ids
            result = get_client().api(
                "GET", "/reservation/v1/resource-reservations", params=params, full=True,
            )
            return ok({"reservations": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_reservation_create(
        resource_id: str,
        subject: str,
        started_at: str,
        ended_at: str,
        attendee_ids: str = "",
        extra_json: str = "",
    ) -> str:
        """자원(회의실 등)을 예약합니다. (POST /reservation/v1/resource-reservations)

        Args:
            resource_id: 자원 ID (필수, dooray_resources로 확인)
            subject: 예약 제목 (필수)
            started_at: 시작 시각 (ISO 형식, 예: "2026-07-10T14:00:00+09:00")
            ended_at: 종료 시각 (ISO 형식)
            attendee_ids: 참석자 조직 멤버 ID (쉼표 구분)
            extra_json: 추가 바디 필드 JSON (예: '{"wholeDayFlag": false}')
        """
        try:
            payload = {
                "resourceId": resource_id,
                "subject": subject,
                "startedAt": started_at,
                "endedAt": ended_at,
            }
            ids = split_ids(attendee_ids)
            if ids:
                payload["users"] = {"to": member_refs(ids)}
            extra = parse_json(extra_json, "extra_json", dict)
            if extra:
                payload.update(extra)
            return ok(get_client().api(
                "POST", "/reservation/v1/resource-reservations", payload=payload,
            ))
        except Exception as e:
            logger.error(f"reservation_create 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_reservation_get(reservation_id: str) -> str:
        """자원 예약 상세 정보를 조회합니다. (GET /reservation/v1/resource-reservations/{id})

        Args:
            reservation_id: 예약 ID (필수)
        """
        try:
            return ok(get_client().api(
                "GET", f"/reservation/v1/resource-reservations/{reservation_id}",
            ))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_reservation_update(reservation_id: str, body_json: str) -> str:
        """자원 예약을 수정합니다. (PUT /reservation/v1/resource-reservations/{id})

        Args:
            reservation_id: 예약 ID (필수)
            body_json: 수정 바디 JSON (예: '{"subject": "회의명 변경", "startedAt": "...", "endedAt": "..."}')
        """
        try:
            payload = parse_json(body_json, "body_json", dict)
            if not payload:
                raise ValidationError("body_json이 비어있습니다.")
            get_client().api(
                "PUT", f"/reservation/v1/resource-reservations/{reservation_id}",
                payload=payload,
            )
            return ok({"message": f"예약 수정 완료: {reservation_id}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_reservation_delete(reservation_id: str, confirm: bool = False) -> str:
        """자원 예약을 취소(삭제)합니다. (DELETE /reservation/v1/resource-reservations/{id})

        Args:
            reservation_id: 취소할 예약 ID (필수)
            confirm: 삭제 확인 (true여야 실제 삭제)
        """
        try:
            if not confirm:
                return need_confirm("자원 예약 취소", reservation_id)
            get_client().api(
                "DELETE", f"/reservation/v1/resource-reservations/{reservation_id}",
            )
            return ok({"message": f"예약 취소 완료: {reservation_id}"})
        except Exception as e:
            return err(e)
