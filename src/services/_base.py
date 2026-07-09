"""서비스 툴 공통 헬퍼 — 응답 직렬화 / JSON 파라미터 파싱 / 확인(confirm) 패턴"""

from __future__ import annotations

import json
import logging

from ..validators import ValidationError

logger = logging.getLogger("dooray-mcp")


def ok(data) -> str:
    """성공 응답을 JSON 문자열로 변환"""
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def err(e: Exception) -> str:
    """에러를 사용자 친화적 JSON 문자열로 변환"""
    return json.dumps({"error": True, "message": str(e)}, ensure_ascii=False, indent=2)


def parse_json(json_str: str, name: str, expect: type | None = None):
    """JSON 문자열 파라미터 파싱. 빈 문자열이면 None."""
    if not json_str or not json_str.strip():
        return None
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValidationError(f"{name} JSON 파싱 실패: {e}")
    if expect is not None and not isinstance(data, expect):
        raise ValidationError(f"{name}은(는) {expect.__name__} 형식이어야 합니다.")
    return data


def split_ids(ids: str) -> list[str]:
    """쉼표 구분 ID 문자열 → 리스트"""
    return [i.strip() for i in ids.split(",") if i.strip()] if ids else []


def need_confirm(action: str, target: str) -> str:
    """위험 작업 확인 요청 응답"""
    return ok({
        "confirm_required": True,
        "message": f"[주의] {action}: {target}\n이 작업은 되돌릴 수 없습니다.",
        "안내": "진행하려면 confirm=true로 다시 호출하세요.",
    })


def markdown_body(content: str) -> dict:
    """Dooray 마크다운 body 객체 생성"""
    return {"mimeType": "text/x-markdown", "content": content or ""}


def member_refs(member_ids: list[str]) -> list[dict]:
    """멤버 ID 목록 → Dooray users 참조 형식"""
    return [
        {"type": "member", "member": {"organizationMemberId": mid}}
        for mid in member_ids
    ]
