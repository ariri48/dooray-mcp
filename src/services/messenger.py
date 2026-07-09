"""Messenger API — 메신저 채널 및 메시지 관리

엔드포인트:
- POST /messenger/v1/channels/direct-send
- GET  /messenger/v1/channels
- POST /messenger/v1/channels?idType={email|member-id}
- POST /messenger/v1/channels/{channel-id}/members/join
- POST /messenger/v1/channels/{channel-id}/members/leave
- POST /messenger/v1/channels/{channel-id}/logs
- PUT/DELETE /messenger/v1/channels/{channel-id}/logs/{log-id}
- POST .../logs/{log-id}/reply
- POST .../threads/create-and-send
- POST .../logs/{log-id}/threads/create-and-send
"""

from __future__ import annotations

from ..validators import ValidationError
from ._base import err, logger, need_confirm, ok, parse_json, split_ids


def register(mcp, get_client):

    @mcp.tool()
    def dooray_messenger_direct_send(organization_member_id: str, text: str) -> str:
        """특정 멤버에게 1:1 메시지를 보냅니다. (POST /messenger/v1/channels/direct-send)

        Args:
            organization_member_id: 받는 사람의 조직 멤버 ID (필수, dooray_common_list_members로 검색)
            text: 메시지 내용 (필수)
        """
        try:
            if not text or not text.strip():
                raise ValidationError("메시지 내용이 비어있습니다.")
            get_client().api(
                "POST", "/messenger/v1/channels/direct-send",
                payload={"organizationMemberId": organization_member_id, "text": text},
            )
            return ok({"message": f"1:1 메시지 발송 완료 → {organization_member_id}"})
        except Exception as e:
            logger.error(f"messenger_direct_send 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_messenger_channels(page: int = 0, size: int = 100) -> str:
        """참여 중인 메신저 채널 목록을 조회합니다. (GET /messenger/v1/channels)

        Args:
            page: 페이지 번호
            size: 페이지 크기
        """
        try:
            result = get_client().api(
                "GET", "/messenger/v1/channels",
                params={"page": page, "size": size}, full=True,
            )
            return ok({"channels": result["result"], "totalCount": result["totalCount"]})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_messenger_channel_create(
        title: str,
        id_list: str,
        id_type: str = "member-id",
        channel_type: str = "private",
        capacity: int = 100,
    ) -> str:
        """메신저 채널을 생성합니다. (POST /messenger/v1/channels?idType={email|member-id})

        Args:
            title: 채널 이름 (필수)
            id_list: 초대할 멤버 (쉼표 구분, 필수 — id_type에 따라 이메일 또는 멤버 ID)
            id_type: ID 형식 (member-id | email)
            channel_type: 채널 종류 (private | direct)
            capacity: 채널 정원 (기본 100)
        """
        try:
            ids = split_ids(id_list)
            if not ids:
                raise ValidationError("id_list가 비어있습니다.")
            payload = {
                "type": channel_type,
                "title": title,
                "idList": ids,
                "capacity": capacity,
            }
            return ok(get_client().api(
                "POST", "/messenger/v1/channels",
                params={"idType": id_type}, payload=payload,
            ))
        except Exception as e:
            logger.error(f"messenger_channel_create 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_messenger_channel_join(channel_id: str, member_ids: str) -> str:
        """멤버를 채널에 초대합니다. (POST /messenger/v1/channels/{channel-id}/members/join)

        Args:
            channel_id: 채널 ID (필수)
            member_ids: 초대할 조직 멤버 ID (쉼표 구분, 필수)
        """
        try:
            ids = split_ids(member_ids)
            if not ids:
                raise ValidationError("member_ids가 비어있습니다.")
            get_client().api(
                "POST", f"/messenger/v1/channels/{channel_id}/members/join",
                payload={"memberIds": ids},
            )
            return ok({"message": f"채널 초대 완료: {len(ids)}명"})
        except Exception as e:
            logger.error(f"messenger_channel_join 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_messenger_channel_leave(channel_id: str, member_ids: str) -> str:
        """멤버를 채널에서 내보냅니다. (POST /messenger/v1/channels/{channel-id}/members/leave)

        Args:
            channel_id: 채널 ID (필수)
            member_ids: 내보낼 조직 멤버 ID (쉼표 구분, 필수)
        """
        try:
            ids = split_ids(member_ids)
            if not ids:
                raise ValidationError("member_ids가 비어있습니다.")
            get_client().api(
                "POST", f"/messenger/v1/channels/{channel_id}/members/leave",
                payload={"memberIds": ids},
            )
            return ok({"message": f"채널 내보내기 완료: {len(ids)}명"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_messenger_send(channel_id: str, text: str) -> str:
        """채널에 메시지를 보냅니다. (POST /messenger/v1/channels/{channel-id}/logs)

        Args:
            channel_id: 채널 ID (필수, dooray_messenger_channels로 확인)
            text: 메시지 내용 (필수)
        """
        try:
            if not text or not text.strip():
                raise ValidationError("메시지 내용이 비어있습니다.")
            return ok(get_client().api(
                "POST", f"/messenger/v1/channels/{channel_id}/logs",
                payload={"text": text},
            ))
        except Exception as e:
            logger.error(f"messenger_send 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_messenger_update_log(channel_id: str, log_id: str, text: str) -> str:
        """채널 메시지를 수정합니다. (PUT /messenger/v1/channels/{channel-id}/logs/{log-id})

        Args:
            channel_id: 채널 ID (필수)
            log_id: 메시지(로그) ID (필수)
            text: 새 메시지 내용 (필수)
        """
        try:
            get_client().api(
                "PUT", f"/messenger/v1/channels/{channel_id}/logs/{log_id}",
                payload={"text": text},
            )
            return ok({"message": f"메시지 수정 완료: {log_id}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_messenger_delete_log(channel_id: str, log_id: str, confirm: bool = False) -> str:
        """채널 메시지를 삭제합니다. (DELETE /messenger/v1/channels/{channel-id}/logs/{log-id})

        Args:
            channel_id: 채널 ID (필수)
            log_id: 삭제할 메시지(로그) ID (필수)
            confirm: 삭제 확인 (true여야 실제 삭제)
        """
        try:
            if not confirm:
                return need_confirm("메시지 삭제", log_id)
            get_client().api(
                "DELETE", f"/messenger/v1/channels/{channel_id}/logs/{log_id}",
            )
            return ok({"message": f"메시지 삭제 완료: {log_id}"})
        except Exception as e:
            return err(e)

    @mcp.tool()
    def dooray_messenger_reply(channel_id: str, log_id: str, text: str) -> str:
        """특정 메시지에 답장을 보냅니다. (POST .../logs/{log-id}/reply)

        Args:
            channel_id: 채널 ID (필수)
            log_id: 답장할 메시지(로그) ID (필수)
            text: 답장 내용 (필수)
        """
        try:
            if not text or not text.strip():
                raise ValidationError("메시지 내용이 비어있습니다.")
            return ok(get_client().api(
                "POST", f"/messenger/v1/channels/{channel_id}/logs/{log_id}/reply",
                payload={"text": text},
            ))
        except Exception as e:
            logger.error(f"messenger_reply 실패: {e}")
            return err(e)

    @mcp.tool()
    def dooray_messenger_thread_send(
        channel_id: str,
        text: str,
        log_id: str = "",
    ) -> str:
        """스레드를 생성하고 메시지를 보냅니다.

        log_id 지정 시 해당 메시지에서 스레드 생성 (POST .../logs/{log-id}/threads/create-and-send),
        미지정 시 채널에서 스레드 생성 (POST .../threads/create-and-send).

        Args:
            channel_id: 채널 ID (필수)
            text: 메시지 내용 (필수)
            log_id: 스레드를 시작할 메시지(로그) ID (선택)
        """
        try:
            if not text or not text.strip():
                raise ValidationError("메시지 내용이 비어있습니다.")
            if log_id:
                path = f"/messenger/v1/channels/{channel_id}/logs/{log_id}/threads/create-and-send"
            else:
                path = f"/messenger/v1/channels/{channel_id}/threads/create-and-send"
            return ok(get_client().api("POST", path, payload={"text": text}))
        except Exception as e:
            logger.error(f"messenger_thread_send 실패: {e}")
            return err(e)
