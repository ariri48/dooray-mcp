"""슬래시 명령어 핸들러 (AI 없이, 무료)

등록된 명령어 → MCP Tool 직접 호출 → 결과 포맷팅 → 두레이 메신저 응답
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from src.client import DoorayClient
from src.validators import ValidationError, clean_task_for_display

_client: DoorayClient | None = None


def get_client() -> DoorayClient:
    global _client
    if _client is None:
        _client = DoorayClient()
    return _client


# ── 명령어 레지스트리 ──────────────────────────────────────

COMMANDS: dict[str, dict] = {}


def command(name: str, description: str, usage: str = ""):
    """명령어 데코레이터"""
    def decorator(func):
        COMMANDS[name] = {
            "handler": func,
            "description": description,
            "usage": usage,
        }
        return func
    return decorator


# ── 슬래시 명령어 구현 ────────────────────────────────────


@command("도움말", "사용 가능한 명령어 목록", "/도움말")
def cmd_help(args: str) -> str:
    lines = ["**사용 가능한 명령어**", ""]
    for name, info in sorted(COMMANDS.items()):
        usage = info["usage"] or f"/{name}"
        lines.append(f"- `{usage}` - {info['description']}")
    lines.append("")
    lines.append("복잡한 요청은 `/ai 자연어 질문` 으로 AI에게 물어보세요.")
    return "\n".join(lines)


@command("내태스크", "나에게 배정된 태스크 조회", "/내태스크 [프로젝트]")
def cmd_my_tasks(args: str) -> str:
    client = get_client()
    project = args.strip() or None
    tasks = client.list_my_tasks(project)
    if not tasks:
        return "배정된 태스크가 없습니다."

    lines = [f"**내 태스크 ({len(tasks)}건)**", ""]
    for t in tasks[:15]:
        c = clean_task_for_display(t)
        ms = c.get("단계", "")
        lines.append(f"- [{c['상태']}] {c['제목']}" + (f" ({ms})" if ms else ""))
    if len(tasks) > 15:
        lines.append(f"  ... 외 {len(tasks) - 15}건")
    return "\n".join(lines)


@command("현황", "프로젝트 현황 요약", "/현황 [프로젝트]")
def cmd_summary(args: str) -> str:
    client = get_client()
    project = args.strip() or None
    result = client.project_summary(project)

    lines = [f"**프로젝트 현황 (총 {result['총_건수']}건)**", ""]

    lines.append("**상태별**")
    for status, count in result["상태별"].items():
        lines.append(f"  - {status}: {count}건")

    lines.append("")
    lines.append("**담당자별**")
    for name, count in list(result["담당자별"].items())[:10]:
        lines.append(f"  - {name}: {count}건")

    return "\n".join(lines)


@command("주간보고", "최근 7일 변경사항 요약", "/주간보고 [프로젝트] [일수]")
def cmd_weekly(args: str) -> str:
    client = get_client()
    parts = args.strip().split()
    project = parts[0] if parts else None
    days = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 7

    result = client.get_weekly_changes(project, days)

    lines = [f"**주간보고 ({result['기간']})**", ""]
    lines.append(f"**{result['요약']}**")

    if result["신규"]["건수"]:
        lines.append("")
        lines.append(f"**신규 ({result['신규']['건수']}건)**")
        for t in result["신규"]["목록"][:10]:
            assignees = ", ".join(t.get("담당자", [])) or "미지정"
            lines.append(f"  - {t['제목']} ({assignees})")

    if result["완료"]["건수"]:
        lines.append("")
        lines.append(f"**완료 ({result['완료']['건수']}건)**")
        for t in result["완료"]["목록"][:10]:
            lines.append(f"  - {t['제목']}")

    if result["수정"]["건수"]:
        lines.append("")
        lines.append(f"**변경 ({result['수정']['건수']}건)**")
        for t in result["수정"]["목록"][:10]:
            lines.append(f"  - {t['제목']}")

    return "\n".join(lines)


@command("방치", "N일 이상 방치된 태스크", "/방치 [프로젝트] [일수]")
def cmd_stale(args: str) -> str:
    client = get_client()
    parts = args.strip().split()
    project = parts[0] if parts else None
    days = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 7

    stale = client.find_stale_tasks(project, days)
    if not stale:
        return f"{days}일 이상 방치된 태스크가 없습니다."

    lines = [f"**{days}일 이상 방치 ({len(stale)}건)**", ""]
    for t in stale[:15]:
        c = clean_task_for_display(t)
        assignees = ", ".join(c.get("담당자", [])) or "미지정"
        lines.append(f"  - {c['제목']} (담당: {assignees}, 수정: {c.get('수정일', '?')})")
    if len(stale) > 15:
        lines.append(f"  ... 외 {len(stale) - 15}건")
    return "\n".join(lines)


@command("품질", "태스크 품질 점검 (누락 항목)", "/품질 [프로젝트]")
def cmd_quality(args: str) -> str:
    client = get_client()
    project = args.strip() or None
    result = client.audit_task_quality(project)

    lines = [f"**태스크 품질 점검 ({result['총_점검']}건 대상)**", ""]
    for issue_type, data in result["이슈"].items():
        if data["건수"] > 0:
            lines.append(f"**{issue_type}: {data['건수']}건**")
            for item in data["목록"][:5]:
                lines.append(f"  - {item['제목']}")
            if data["건수"] > 5:
                lines.append(f"  ... 외 {data['건수'] - 5}건")
            lines.append("")

    if all(d["건수"] == 0 for d in result["이슈"].values()):
        lines.append("모든 항목 정상!")

    return "\n".join(lines)


@command("검색", "태스크 제목 검색", "/검색 검색어 [프로젝트]")
def cmd_search(args: str) -> str:
    client = get_client()
    parts = args.strip().split(maxsplit=1)
    if not parts:
        return "사용법: `/검색 검색어 [프로젝트]`"

    keyword = parts[0]
    project = parts[1] if len(parts) > 1 else None

    all_tasks = client.list_all_tasks(project)
    kw = keyword.lower()
    matched = [t for t in all_tasks if kw in t.get("subject", "").lower()]

    if not matched:
        return f"'{keyword}' 검색 결과가 없습니다."

    lines = [f"**'{keyword}' 검색 결과 ({len(matched)}건)**", ""]
    for t in matched[:15]:
        c = clean_task_for_display(t)
        lines.append(f"  - [{c['상태']}] {c['제목']}")
    if len(matched) > 15:
        lines.append(f"  ... 외 {len(matched) - 15}건")
    return "\n".join(lines)


@command("중복", "중복 태스크 탐지", "/중복 [프로젝트]")
def cmd_duplicates(args: str) -> str:
    client = get_client()
    project = args.strip() or None
    dups = client.find_duplicates(project)

    if not dups:
        return "중복 태스크가 없습니다."

    lines = [f"**중복 태스크 ({len(dups)}그룹)**", ""]
    for d in dups[:10]:
        lines.append(f"- **{d['정규화_제목']}** ({d['건수']}건)")
        for t in d["태스크"]:
            lines.append(f"  - [{t['상태']}] {t['제목']} ({t['id']})")
    return "\n".join(lines)


@command("파이프라인", "파트너 신청 단계별 현황", "/파이프라인 [프로젝트]")
def cmd_pipeline(args: str) -> str:
    client = get_client()
    project = args.strip() or None
    result = client.get_partner_pipeline_status(project)

    lines = [f"**파이프라인 현황 (총 {result['총_건수']}건)**", ""]
    for stage in result["파이프라인"]:
        active = stage["진행중"]
        total = stage["전체"]
        bar = "=" * min(active, 20)
        lines.append(f"  {stage['단계']:15s} | {bar} {active}/{total}")
    return "\n".join(lines)


# ── 명령어 실행 ────────────────────────────────────────────


def execute_command(text: str) -> str | None:
    """슬래시 명령어 파싱 + 실행.

    Returns:
        응답 텍스트 (명령어가 아니면 None)
    """
    text = text.strip()
    if not text.startswith("/"):
        return None

    parts = text[1:].split(maxsplit=1)
    cmd_name = parts[0]
    cmd_args = parts[1] if len(parts) > 1 else ""

    if cmd_name not in COMMANDS:
        return None

    try:
        return COMMANDS[cmd_name]["handler"](cmd_args)
    except ValidationError as e:
        return f"오류: {e}"
    except Exception as e:
        return f"처리 중 오류 발생: {e}"
