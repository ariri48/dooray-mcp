"""연결 검증 스크립트 — .env 설정 후 실제 Dooray API 연결 테스트

실행: python -m tests.test_connection
결과: 각 API 엔드포인트별 성공/실패 리포트
"""

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.client import DoorayClient
from src.validators import ValidationError


def run_connection_test():
    """Dooray API 연결 및 기본 기능 검증"""
    print("=" * 60)
    print("  Dooray MCP - 연결 검증")
    print("=" * 60)
    print()

    results = []

    # 1. 클라이언트 초기화
    print("[1/7] 클라이언트 초기화...", end=" ")
    try:
        client = DoorayClient()
        print(f"OK (tenant: {client.tenant_id})")
        results.append(("클라이언트 초기화", True, ""))
    except ValidationError as e:
        print(f"FAIL: {e}")
        results.append(("클라이언트 초기화", False, str(e)))
        _print_summary(results)
        return

    project_id = client.default_project_id
    if not project_id:
        print("\n[경고] DOORAY_DEFAULT_PROJECT_ID가 미설정입니다.")
        print("       .env에 기본 프로젝트 ID를 설정하면 더 많은 테스트를 수행합니다.")
        _print_summary(results)
        return

    # 2. 태그 목록 조회
    print(f"[2/7] 태그 목록 조회 (project: {project_id})...", end=" ")
    try:
        tags = client.list_tags(project_id)
        print(f"OK ({len(tags)}개)")
        results.append(("태그 목록", True, f"{len(tags)}개"))
    except Exception as e:
        print(f"FAIL: {e}")
        results.append(("태그 목록", False, str(e)))

    # 3. 멤버 목록 조회
    print("[3/7] 멤버 목록 조회...", end=" ")
    try:
        members = client.list_members(project_id)
        print(f"OK ({len(members)}명)")
        results.append(("멤버 목록", True, f"{len(members)}명"))
    except Exception as e:
        print(f"FAIL: {e}")
        results.append(("멤버 목록", False, str(e)))

    # 4. 워크플로우 조회
    print("[4/7] 워크플로우 조회...", end=" ")
    try:
        workflows = client.list_workflows(project_id)
        print(f"OK ({len(workflows)}개)")
        results.append(("워크플로우", True, f"{len(workflows)}개"))
    except Exception as e:
        print(f"FAIL: {e}")
        results.append(("워크플로우", False, str(e)))

    # 5. 마일스톤 조회
    print("[5/7] 마일스톤 조회...", end=" ")
    try:
        milestones = client.list_milestones(project_id)
        print(f"OK ({len(milestones)}개)")
        results.append(("마일스톤", True, f"{len(milestones)}개"))
    except Exception as e:
        print(f"FAIL: {e}")
        results.append(("마일스톤", False, str(e)))

    # 6. 태스크 목록 조회 (1페이지만)
    print("[6/7] 태스크 목록 조회 (1페이지)...", end=" ")
    try:
        result = client.list_tasks(project_id, page=0, size=5)
        count = len(result["tasks"])
        print(f"OK ({count}건)")
        results.append(("태스크 목록", True, f"{count}건"))

        # 7. 단일 태스크 상세 (첫 번째 태스크)
        if result["tasks"]:
            first_id = result["tasks"][0]["id"]
            print(f"[7/7] 단일 태스크 상세 조회 ({first_id})...", end=" ")
            try:
                task = client.get_task(first_id, project_id)
                print(f"OK ('{task.get('subject', '?')}')")
                results.append(("태스크 상세", True, task.get("subject", "")))
            except Exception as e:
                print(f"FAIL: {e}")
                results.append(("태스크 상세", False, str(e)))
        else:
            print("[7/7] 태스크가 없어 상세 조회 건너뜀")
            results.append(("태스크 상세", None, "태스크 없음"))
    except Exception as e:
        print(f"FAIL: {e}")
        results.append(("태스크 목록", False, str(e)))

    _print_summary(results)


def _print_summary(results):
    print()
    print("=" * 60)
    print("  검증 결과 요약")
    print("=" * 60)
    passed = sum(1 for _, ok, _ in results if ok is True)
    failed = sum(1 for _, ok, _ in results if ok is False)
    skipped = sum(1 for _, ok, _ in results if ok is None)

    for name, ok, detail in results:
        status = "PASS" if ok else ("SKIP" if ok is None else "FAIL")
        icon = "  " if ok else ("  " if ok is None else "  ")
        print(f"  {icon} {status}: {name}" + (f" - {detail}" if detail else ""))

    print()
    print(f"  합계: {passed} 통과 / {failed} 실패 / {skipped} 건너뜀")

    if failed == 0:
        print()
        print("  Dooray MCP 서버를 사용할 준비가 되었습니다!")
    else:
        print()
        print("  .env 설정을 확인하고 다시 시도하세요.")


if __name__ == "__main__":
    run_connection_test()
