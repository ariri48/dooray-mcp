"""감사 로그 - 팀 환경에서 누가 무엇을 했는지 기록

로그 파일: dooray-mcp/logs/audit.jsonl (줄 단위 JSON)
각 팀원의 로컬에 저장되므로 개인 활동 기록용.

기록 대상: 쓰기 작업 (create, update, delete, move, comment, webhook)
읽기 작업은 기록하지 않음 (노이즈 방지).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "audit.jsonl")


def log_action(
    action: str,
    target: str,
    details: dict | None = None,
    project_id: str = "",
) -> None:
    """감사 로그 기록.

    Args:
        action: 작업 유형 (create_task, update_task, delete_task, add_comment, move_task, send_webhook)
        target: 대상 (post_id 또는 설명)
        details: 추가 정보
        project_id: 프로젝트 ID
    """
    os.makedirs(_LOG_DIR, exist_ok=True)

    entry = {
        "timestamp": datetime.now(KST).isoformat(),
        "action": action,
        "target": target,
        "project_id": project_id,
    }
    if details:
        entry["details"] = details

    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # 로깅 실패가 본 작업을 방해하면 안 됨


def get_recent_logs(limit: int = 50) -> list[dict]:
    """최근 감사 로그 조회.

    Args:
        limit: 최대 조회 건수 (기본 50)

    Returns:
        최근 로그 리스트 (최신순)
    """
    if not os.path.isfile(_LOG_FILE):
        return []

    lines = []
    try:
        with open(_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []

    # 최신순으로 limit개
    entries = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(entries) >= limit:
            break

    return entries
