"""Calendar API — 캘린더 및 일정 관리

엔드포인트:
- POST   /calendar/v1/calendars
- GET    /calendar/v1/calendars
- GET    /calendar/v1/calendars/{calendar-id}
- DELETE /calendar/v1/calendars/{calendar-id}
- PUT    /calendar/v1/calendars/{calendar-id}/members
- POST   /calendar/v1/calendars/{calendar-id}/events
- GET    /calendar/v1/calendars/*/events
- GET    /calendar/v1/calendars/{calendar-id}/events/{event-id}
- PUT    /calendar/v1/calendars/{calendar-id}/events/{event-id}
- POST   /calendar/v1/calendars/{calendar-id}/events/{event-id}/delete
"""

from __future__ import annotations

from ..validators import ValidationError
from ._base import (
    err, logger, markdown_body, member_refs, need_confirm, ok, parse_json, split_ids,
)


def register(mcp, get_client):

    @mcp.tool()
    def dooray_calendar_create(name: str, body_json: str = "") -> str:
        """새 캘린더를 생성합니다. (POST /calendar/v1/calendars)

        Args:
            name: 캘린더 이름 (필수)
            body_json: 추가 바디 필드 JSON (예: '{"me": {"color": "#FF0000"}, "notifications": []}')
        """
        try:
            payload = {"name": name}
            extra = parse_json(body_json, "body_json", dict)
            if extra:
                payload.update(extra)
            return ok(get_client().api("POST", "/calendar/v1/calendars", payload=payload))
        except Exception as e:
            logger.error(f"calendar_create 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_calendar_list() -> str:
        """접근 가능한 캘린더 목록을 조회합니다. (GET /calendar/v1/calendars)"""
        try:
            result = get_client().api("GET", "/calendar/v1/calendars", full=True)
            return ok({"calendars": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_calendar_get(calendar_id: str) -> str:
        """캘린더 상세 정보를 조회합니다. (GET /calendar/v1/calendars/{calendar-id})

        Args:
            calendar_id: 캘린더 ID (필수)
        """
        try:
            return ok(get_client().api("GET", f"/calendar/v1/calendars/{calendar_id}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_calendar_delete(calendar_id: str, confirm: bool = False) -> str:
        """캘린더를 삭제합니다. (DELETE /calendar/v1/calendars/{calendar-id})

        Args:
            calendar_id: 삭제할 캘린더 ID (필수)
            confirm: 삭제 확인 (true여야 실제 삭제)
        """
        try:
            if not confirm:
                return need_confirm("캘린더 삭제", calendar_id)
            get_client().api("DELETE", f"/calendar/v1/calendars/{calendar_id}")
            return ok({"message": f"캘린더 삭제 완료: {calendar_id}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_calendar_update_members(calendar_id: str, members_json: str) -> str:
        """캘린더 구성원을 수정합니다. (PUT /calendar/v1/calendars/{calendar-id}/members)

        Args:
            calendar_id: 캘린더 ID (필수)
            members_json: 구성원 정의 JSON 배열. 예:
                '[{"type": "member", "member": {"organizationMemberId": "123"}, "role": "delegatee"}]'
        """
        try:
            members = parse_json(members_json, "members_json", list)
            if not members:
                raise ValidationError("members_json이 비어있습니다.")
            get_client().api(
                "PUT", f"/calendar/v1/calendars/{calendar_id}/members",
                payload={"members": members},
            )
            return ok({"message": f"캘린더 구성원 수정 완료: {calendar_id}"})
        except Exception as e:
            logger.error(f"calendar_update_members 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_calendar_create_event(
        calendar_id: str,
        subject: str,
        started_at: str,
        ended_at: str,
        body_md: str = "",
        location: str = "",
        whole_day: bool = False,
        attendee_ids: str = "",
        cc_ids: str = "",
        extra_json: str = "",
    ) -> str:
        """캘린더에 일정을 생성합니다. (POST /calendar/v1/calendars/{calendar-id}/events)

        Args:
            calendar_id: 캘린더 ID (필수, dooray_calendar_list로 확인)
            subject: 일정 제목 (필수)
            started_at: 시작 시각 (ISO 형식, 예: "2026-07-10T14:00:00+09:00")
            ended_at: 종료 시각 (ISO 형식, 예: "2026-07-10T15:00:00+09:00")
            body_md: 일정 내용 (마크다운)
            location: 장소
            whole_day: 종일 일정 여부
            attendee_ids: 참석자 조직 멤버 ID (쉼표 구분)
            cc_ids: 참조자 조직 멤버 ID (쉼표 구분)
            extra_json: 추가 바디 필드 JSON (예: '{"recurrenceRule": {...}, "personalSettings": {"alarms": [{"action": "app", "trigger": "TRIGGER:-PT10M"}]}}')
        """
        try:
            payload = {
                "subject": subject,
                "startedAt": started_at,
                "endedAt": ended_at,
                "wholeDayFlag": whole_day,
                "body": markdown_body(body_md),
            }
            if location:
                payload["location"] = location
            users = {}
            to_ids = split_ids(attendee_ids)
            ccs = split_ids(cc_ids)
            if to_ids:
                users["to"] = member_refs(to_ids)
            if ccs:
                users["cc"] = member_refs(ccs)
            if users:
                payload["users"] = users
            extra = parse_json(extra_json, "extra_json", dict)
            if extra:
                payload.update(extra)
            return ok(get_client().api(
                "POST", f"/calendar/v1/calendars/{calendar_id}/events", payload=payload,
            ))
        except Exception as e:
            logger.error(f"calendar_create_event 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_calendar_list_events(
        time_min: str,
        time_max: str,
        calendars: str = "",
        params_json: str = "",
    ) -> str:
        """기간 내 일정 목록을 조회합니다. (GET /calendar/v1/calendars/*/events)

        Args:
            time_min: 조회 시작 시각 (ISO 형식, 예: "2026-07-01T00:00:00+09:00")
            time_max: 조회 종료 시각 (ISO 형식, 예: "2026-07-31T23:59:59+09:00")
            calendars: 조회할 캘린더 ID (쉼표 구분, 미지정 시 전체)
            params_json: 추가 쿼리 파라미터 JSON (예: '{"postType": "toMe", "category": "general"}')
        """
        try:
            params = {"timeMin": time_min, "timeMax": time_max}
            if calendars:
                params["calendars"] = calendars
            extra = parse_json(params_json, "params_json", dict)
            if extra:
                params.update(extra)
            result = get_client().api(
                "GET", "/calendar/v1/calendars/*/events", params=params, full=True,
            )
            return ok({"events": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            logger.error(f"calendar_list_events 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_calendar_get_event(calendar_id: str, event_id: str) -> str:
        """일정 상세 정보를 조회합니다. (GET /calendar/v1/calendars/{calendar-id}/events/{event-id})

        Args:
            calendar_id: 캘린더 ID (필수)
            event_id: 일정 ID (필수)
        """
        try:
            return ok(get_client().api(
                "GET", f"/calendar/v1/calendars/{calendar_id}/events/{event_id}",
            ))
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_calendar_update_event(
        calendar_id: str,
        event_id: str,
        subject: str = "",
        started_at: str = "",
        ended_at: str = "",
        body_md: str = "",
        location: str = "",
        extra_json: str = "",
    ) -> str:
        """일정을 수정합니다. 변경할 필드만 입력하세요. (PUT /calendar/v1/calendars/{calendar-id}/events/{event-id})

        Args:
            calendar_id: 캘린더 ID (필수)
            event_id: 일정 ID (필수)
            subject: 새 제목
            started_at: 새 시작 시각 (ISO 형식)
            ended_at: 새 종료 시각 (ISO 형식)
            body_md: 새 내용 (마크다운)
            location: 새 장소
            extra_json: 추가 바디 필드 JSON
        """
        try:
            payload = {}
            if subject:
                payload["subject"] = subject
            if started_at:
                payload["startedAt"] = started_at
            if ended_at:
                payload["endedAt"] = ended_at
            if body_md:
                payload["body"] = markdown_body(body_md)
            if location:
                payload["location"] = location
            extra = parse_json(extra_json, "extra_json", dict)
            if extra:
                payload.update(extra)
            if not payload:
                raise ValidationError("변경할 내용이 없습니다.")
            get_client().api(
                "PUT", f"/calendar/v1/calendars/{calendar_id}/events/{event_id}",
                payload=payload,
            )
            return ok({"message": f"일정 수정 완료: {event_id}", "변경": list(payload.keys())})
        except Exception as e:
            logger.error(f"calendar_update_event 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_calendar_delete_event(
        calendar_id: str,
        event_id: str,
        confirm: bool = False,
        delete_type: str = "",
    ) -> str:
        """일정을 삭제합니다. (POST /calendar/v1/calendars/{calendar-id}/events/{event-id}/delete)

        Args:
            calendar_id: 캘린더 ID (필수)
            event_id: 삭제할 일정 ID (필수)
            confirm: 삭제 확인 (true여야 실제 삭제)
            delete_type: 반복 일정 삭제 범위 (this | fromThis | all)
        """
        try:
            if not confirm:
                return need_confirm("일정 삭제", event_id)
            payload = {"deleteType": delete_type} if delete_type else {}
            get_client().api(
                "POST", f"/calendar/v1/calendars/{calendar_id}/events/{event_id}/delete",
                payload=payload,
            )
            return ok({"message": f"일정 삭제 완료: {event_id}"})
        except Exception as e:
            return err(e)
