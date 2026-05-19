"""프로젝트 별칭 시스템 - 20개 프로젝트를 이름으로 접근

사용법:
    "파트너신청" → "4118231653304784792"
    "영업대행수수료" → "3673354057796392405"

projects.json 구조:
{
    "파트너신청": {"id": "4118231653304784792", "description": "파트너 신청/등록 관리"},
    "영업대행수수료": {"id": "3673354057796392405", "description": "영업대행수수료 신청"},
    ...
}

별칭 해석 우선순위:
1. 숫자 문자열 → 그대로 project_id로 사용
2. projects.json 정확히 매칭 → 해당 ID
3. projects.json 부분 매칭 → 1개면 사용, 2개 이상이면 후보 목록 반환
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from .validators import ValidationError

# projects.json 경로 (dooray-mcp 루트)
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS_FILE = os.path.join(_PROJECT_DIR, "projects.json")


def load_projects() -> dict[str, dict]:
    """projects.json 로드. 없으면 빈 dict."""
    if not os.path.isfile(PROJECTS_FILE):
        return {}
    try:
        with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_projects(projects: dict[str, dict]) -> None:
    """projects.json 저장."""
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)


def get_my_project_id() -> str | None:
    """현재 사용자의 개인 프로젝트 ID 반환. .env의 DOORAY_MY_PROJECT_ID."""
    return os.environ.get("DOORAY_MY_PROJECT_ID", "").strip() or None


# "내 프로젝트"를 가리키는 키워드들
_MY_PROJECT_KEYWORDS = {
    "내프로젝트", "내 프로젝트", "개인", "개인프로젝트", "개인 프로젝트",
    "my", "my_project", "mine", "personal",
}


def resolve_project_alias(name_or_id: str | None, default_id: str | None = None) -> str:
    """별칭 또는 ID를 실제 project_id로 해석.

    Args:
        name_or_id: 프로젝트 별칭("파트너신청") 또는 숫자 ID
            - "내프로젝트", "개인", "my" 등 → .env의 DOORAY_MY_PROJECT_ID 사용
        default_id: 미지정 시 사용할 기본 ID

    Returns:
        실제 project_id (숫자 문자열)

    Raises:
        ValidationError: 해석 실패 시 (후보 목록 포함)
    """
    # None/빈값 → 기본값
    if not name_or_id or not name_or_id.strip():
        if default_id:
            return default_id
        raise ValidationError(
            "project_id가 필요합니다. "
            "프로젝트 이름(별칭) 또는 숫자 ID를 입력하세요. "
            "등록된 프로젝트 목록은 dooray_list_projects를 호출하세요."
        )

    name_or_id = name_or_id.strip()

    # 0. "내 프로젝트" 키워드 → 개인 프로젝트
    if name_or_id.lower().replace(" ", "") in {k.replace(" ", "") for k in _MY_PROJECT_KEYWORDS}:
        my_pid = get_my_project_id()
        if not my_pid:
            raise ValidationError(
                "개인 프로젝트가 설정되지 않았습니다. "
                ".env에 DOORAY_MY_PROJECT_ID를 설정하세요."
            )
        return my_pid

    # 1. 숫자 → 그대로 사용
    if re.match(r"^\d+$", name_or_id):
        return name_or_id

    # 2. 별칭 매칭
    projects = load_projects()
    if not projects:
        raise ValidationError(
            f"'{name_or_id}'은 숫자 ID가 아니고, projects.json이 없습니다. "
            "dooray_discover_projects를 먼저 실행하여 프로젝트 목록을 등록하세요."
        )

    # 정확히 일치
    if name_or_id in projects:
        return projects[name_or_id]["id"]

    # 대소문자 무시 정확 일치
    lower_key = name_or_id.lower()
    for alias, info in projects.items():
        if alias.lower() == lower_key:
            return info["id"]

    # 부분 일치
    candidates = []
    for alias, info in projects.items():
        if lower_key in alias.lower() or lower_key in info.get("description", "").lower():
            candidates.append((alias, info["id"], info.get("description", "")))

    if len(candidates) == 1:
        return candidates[0][1]

    if len(candidates) > 1:
        hint = "\n".join(f"  - {a}: {d} ({pid})" for a, pid, d in candidates)
        raise ValidationError(
            f"'{name_or_id}'에 매칭되는 프로젝트가 {len(candidates)}개입니다. "
            f"더 구체적으로 입력하세요:\n{hint}"
        )

    # 매칭 실패
    available = ", ".join(sorted(projects.keys()))
    raise ValidationError(
        f"'{name_or_id}'에 매칭되는 프로젝트가 없습니다. "
        f"등록된 별칭: {available}"
    )


def list_all_projects() -> list[dict]:
    """등록된 전체 프로젝트 목록 반환."""
    projects = load_projects()
    return [
        {"별칭": alias, "id": info["id"], "설명": info.get("description", "")}
        for alias, info in sorted(projects.items())
    ]


def register_project(alias: str, project_id: str, description: str = "") -> dict:
    """프로젝트 별칭 등록/갱신."""
    if not alias or not alias.strip():
        raise ValidationError("별칭이 비어있습니다.")
    if not re.match(r"^\d+$", str(project_id)):
        raise ValidationError(f"project_id가 올바르지 않습니다: '{project_id}'")

    projects = load_projects()
    projects[alias.strip()] = {
        "id": str(project_id),
        "description": description.strip(),
    }
    save_projects(projects)
    return {"별칭": alias.strip(), "id": str(project_id), "설명": description.strip()}


def unregister_project(alias: str) -> dict:
    """프로젝트 별칭 삭제."""
    projects = load_projects()
    if alias not in projects:
        raise ValidationError(f"'{alias}' 별칭이 등록되어 있지 않습니다.")
    removed = projects.pop(alias)
    save_projects(projects)
    return {"삭제됨": alias, "id": removed["id"]}
