"""자동 업데이트 결과를 사용자에게 한 번 알려 주는 기능.

run_server.py가 서버 시작 때 git pull 결과를 환경변수 DOORAY_MCP_UPDATE_NOTICE에 남기면,
서버는 그 뒤 첫 번째 도구 응답 끝에 안내 한 줄을 붙이고 지운다.
"""

from __future__ import annotations

import os
import re

ENV_KEY = "DOORAY_MCP_UPDATE_NOTICE"
_NETWORK_HINTS = ("could not resolve", "unable to access", "timed out", "network", "connection")


def latest_release(guide_path: str) -> tuple[str, str] | None:
    """GUIDE.md 버전 기록 표의 첫 줄에서 (버전, 내용)을 읽는다."""
    try:
        with open(guide_path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"\|\s*\*{0,2}(v[\d.]+)\*{0,2}\s*\|\s*(.+?)\s*\|\s*$", line)
                if m:
                    return m.group(1), m.group(2)
    except OSError:
        pass
    return None


def build_notice(before: str, after: str, returncode: int, stderr: str, guide_path: str) -> str:
    """git pull 결과로 안내 문구를 만든다. 알릴 게 없으면 빈 문자열."""
    if returncode != 0:
        low = (stderr or "").lower()
        if any(h in low for h in _NETWORK_HINTS):
            return ""  # 오프라인 등 일시적 문제는 알리지 않음
        return (
            "[dooray-mcp 안내] 자동 업데이트에 실패해 이전 버전으로 실행 중입니다. "
            "dooray-mcp 폴더에서 `git pull`을 직접 실행해 주세요. "
            f"(원인: {(stderr or '').strip()[:150]})"
        )
    if before and after and before != after:
        rel = latest_release(guide_path)
        if rel:
            ver, desc = rel
            desc = re.sub(r"\s+", " ", desc)[:200]
            return f"[dooray-mcp 안내] {ver}로 업데이트되었습니다. 바뀐 점: {desc}"
        return "[dooray-mcp 안내] 최신 버전으로 업데이트되었습니다."
    return ""


def pop_notice() -> str:
    """안내 문구를 한 번만 꺼낸다."""
    return os.environ.pop(ENV_KEY, "")


def attach_notice(result):
    """도구 응답(내용 목록 또는 (내용, 구조화) 튜플) 끝에 안내 한 줄을 붙인다."""
    notice = pop_notice()
    if not notice:
        return result
    from mcp.types import TextContent

    block = TextContent(
        type="text",
        text=notice + "\n(이 안내를 사용자에게 한 줄로 전해 주세요.)",
    )
    if isinstance(result, tuple) and result and isinstance(result[0], list):
        return (list(result[0]) + [block],) + tuple(result[1:])
    if isinstance(result, list):
        return result + [block]
    return result
