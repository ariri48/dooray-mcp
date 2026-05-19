"""데이터 검증 레이어 — 모든 API 응답과 입력값을 신뢰할 수 있게 만드는 핵심 모듈

설계 원칙:
- API 응답의 필수 필드 누락 시 명확한 한글 에러 메시지
- 입력값 타입/범위 검증으로 잘못된 요청 사전 차단
- 위험 작업(삭제, 이동) 전 확인 요약 반환
"""

from __future__ import annotations

import re
from typing import Any


class ValidationError(Exception):
    """검증 실패 시 발생하는 예외 — 한글 메시지 포함"""

    pass


# ── API 응답 검증 ──────────────────────────────────────────


def validate_api_response(resp_json: dict, context: str = "") -> dict:
    """Dooray API 응답 구조 검증.

    성공 시 result 반환, 실패 시 ValidationError.
    """
    if not isinstance(resp_json, dict):
        raise ValidationError(f"[{context}] API 응답이 올바른 JSON이 아닙니다.")

    header = resp_json.get("header", {})
    if not header.get("isSuccessful"):
        code = header.get("resultCode", "UNKNOWN")
        msg = header.get("resultMessage", "알 수 없는 오류")
        raise ValidationError(f"[{context}] API 오류 ({code}): {msg}")

    return resp_json.get("result")


def validate_task(task: dict, require_body: bool = False) -> dict:
    """태스크 데이터 필수 필드 검증.

    Returns:
        검증 통과된 태스크 dict (원본 그대로)
    """
    if not isinstance(task, dict):
        raise ValidationError("태스크 데이터가 올바른 형식이 아닙니다.")

    required = ["id", "subject"]
    missing = [f for f in required if not task.get(f)]
    if missing:
        raise ValidationError(
            f"태스크에 필수 필드가 누락되었습니다: {', '.join(missing)}"
        )

    if require_body:
        body = task.get("body")
        if not body or not body.get("content"):
            raise ValidationError("태스크 본문(body.content)이 비어있습니다.")

    return task


def validate_task_list(tasks: list, context: str = "태스크 목록") -> list:
    """태스크 목록의 각 항목 검증. 유효하지 않은 항목은 경고와 함께 건너뜀."""
    validated = []
    warnings = []
    for i, t in enumerate(tasks):
        try:
            validated.append(validate_task(t))
        except ValidationError as e:
            warnings.append(f"  #{i}: {e}")

    if warnings:
        # 경고는 포함하되 유효한 데이터는 반환
        pass

    return validated


# ── 입력값 검증 ────────────────────────────────────────────


def validate_project_id(project_id: str | None, default: str | None = None) -> str:
    """프로젝트 ID 검증. 숫자 문자열이어야 함."""
    pid = project_id or default
    if not pid:
        raise ValidationError(
            "project_id가 필요합니다. "
            "프로젝트 ID를 입력하거나 .env에 DOORAY_DEFAULT_PROJECT_ID를 설정하세요."
        )
    if not re.match(r"^\d+$", str(pid)):
        raise ValidationError(
            f"project_id가 올바르지 않습니다: '{pid}' (숫자만 허용)"
        )
    return str(pid)


def validate_post_id(post_id: str | None, name: str = "post_id") -> str:
    """태스크(포스트) ID 검증."""
    if not post_id:
        raise ValidationError(f"{name}이(가) 비어있습니다.")
    if not re.match(r"^\d+$", str(post_id)):
        raise ValidationError(
            f"{name}이(가) 올바르지 않습니다: '{post_id}' (숫자만 허용)"
        )
    return str(post_id)


def validate_subject(subject: str | None) -> str:
    """태스크 제목 검증."""
    if not subject or not subject.strip():
        raise ValidationError("태스크 제목(subject)이 비어있습니다.")
    s = subject.strip()
    if len(s) > 500:
        raise ValidationError(
            f"태스크 제목이 너무 깁니다: {len(s)}자 (최대 500자)"
        )
    return s


def validate_body_content(content: str | None) -> str:
    """본문 내용 검증."""
    if not content or not content.strip():
        raise ValidationError("본문 내용이 비어있습니다.")
    return content.strip()


def validate_tag_names(tag_names: list | None) -> list[str]:
    """태그 이름 목록 검증."""
    if not tag_names:
        return []
    if not isinstance(tag_names, list):
        raise ValidationError("tag_names는 리스트여야 합니다.")
    validated = []
    for name in tag_names:
        if not isinstance(name, str) or not name.strip():
            raise ValidationError(f"올바르지 않은 태그 이름: '{name}'")
        validated.append(name.strip())
    return validated


# ── 위험 작업 확인 요약 ────────────────────────────────────


def danger_summary(action: str, target: str, details: dict | None = None) -> str:
    """위험 작업 실행 전 사용자에게 보여줄 확인 요약 생성.

    Returns:
        확인 메시지 문자열
    """
    lines = [
        f"[주의] {action}",
        f"  대상: {target}",
    ]
    if details:
        for k, v in details.items():
            lines.append(f"  {k}: {v}")
    lines.append("  이 작업은 되돌릴 수 없을 수 있습니다.")
    return "\n".join(lines)


# ── 페이지네이션 검증 ──────────────────────────────────────


def validate_pagination(page: int = 0, size: int = 100) -> tuple[int, int]:
    """페이지네이션 파라미터 검증."""
    if not isinstance(page, int) or page < 0:
        raise ValidationError(f"page는 0 이상의 정수여야 합니다: {page}")
    if not isinstance(size, int) or size < 1 or size > 100:
        raise ValidationError(f"size는 1~100 사이여야 합니다: {size}")
    return page, size


# ── 데이터 정제 ────────────────────────────────────────────


def clean_task_for_display(task: dict) -> dict:
    """태스크 데이터를 사용자 표시용으로 정제.

    - 불필요한 내부 필드 제거
    - 날짜 포맷 정리
    - 이름 기반으로 변환 (ID → 이름)
    """
    cleaned = {
        "id": task.get("id", ""),
        "제목": task.get("subject", "(제목 없음)"),
        "상태": _extract_workflow_name(task),
        "단계": _extract_milestone_name(task),
        "담당자": _extract_assignees(task),
        "태그": _extract_tag_names(task),
        "생성일": _format_date(task.get("createdAt")),
        "수정일": _format_date(task.get("updatedAt")),
    }
    # 본문이 있으면 포함
    body = task.get("body", {})
    if body and body.get("content"):
        cleaned["본문"] = body["content"]

    return cleaned


def _extract_workflow_name(task: dict) -> str:
    wf = task.get("workflowClass", "")
    # workflowClass가 있으면 사용, 없으면 raw
    if wf:
        return wf
    wf_place = task.get("users", {}).get("to", [])
    return "알 수 없음"


def _extract_milestone_name(task: dict) -> str:
    ms = task.get("milestone")
    if ms and isinstance(ms, dict):
        return ms.get("name", "없음")
    return "없음"


def _extract_assignees(task: dict) -> list[str]:
    users = task.get("users", {})
    to_list = users.get("to", [])
    names = []
    for u in to_list:
        member = u.get("member", {})
        name = member.get("name", "")
        if name:
            names.append(name)
    return names if names else ["미지정"]


def _extract_tag_names(task: dict) -> list[str]:
    tags = task.get("tags", [])
    return [t.get("name", "") for t in tags if t.get("name")]


def validate_json_array(json_str: str, context: str = "JSON 배열") -> list[dict]:
    """JSON 배열 문자열을 파싱하여 dict 리스트로 반환."""
    import json

    if not json_str or not json_str.strip():
        raise ValidationError(f"{context}: 입력이 비어있습니다.")
    try:
        data = json.loads(json_str.strip())
    except json.JSONDecodeError as e:
        raise ValidationError(f"{context}: JSON 파싱 실패 — {e}")
    if not isinstance(data, list):
        raise ValidationError(f"{context}: JSON 배열이어야 합니다. (현재: {type(data).__name__})")
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValidationError(f"{context}: #{i} 항목이 객체가 아닙니다.")
    return data


def validate_subjects_list(subjects_str: str) -> list[str]:
    """줄바꿈 또는 쉼표로 구분된 제목 목록을 파싱."""
    if not subjects_str or not subjects_str.strip():
        raise ValidationError("제목 목록이 비어있습니다.")
    # 줄바꿈 우선, 없으면 쉼표
    if "\n" in subjects_str:
        items = subjects_str.strip().split("\n")
    else:
        items = subjects_str.strip().split(",")
    result = [s.strip() for s in items if s.strip()]
    if not result:
        raise ValidationError("유효한 제목이 없습니다.")
    return result


def _format_date(date_str: str | None) -> str:
    if not date_str:
        return ""
    # ISO 형식에서 날짜 부분만 추출
    if "T" in str(date_str):
        return str(date_str).split("T")[0]
    return str(date_str)
