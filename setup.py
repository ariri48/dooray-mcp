#!/usr/bin/env python3
"""Dooray MCP - 팀원 온보딩 설치 스크립트

이 스크립트 하나로:
1. Dooray API 토큰 입력 안내
2. .env 파일 생성
3. 의존성 설치
4. 연결 검증 (태그/멤버/워크플로우)
5. 프로젝트 자동 탐색 → projects.json 생성
6. Claude Code MCP 서버 등록

실행: python setup.py
"""

import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(SCRIPT_DIR, ".env")
PROJECTS_FILE = os.path.join(SCRIPT_DIR, "projects.json")


def print_header():
    print()
    print("=" * 55)
    print("  Dooray MCP Server - 설치 마법사")
    print("=" * 55)
    print()


def step_1_token():
    """API 토큰 입력"""
    print("[1/5] Dooray API 토큰 설정")
    print()

    if os.path.isfile(ENV_FILE):
        print("  .env 파일이 이미 존재합니다.")
        answer = input("  기존 설정을 유지할까요? (Y/n): ").strip().lower()
        if answer != "n":
            print("  -> 기존 설정 유지")
            return True
        print()

    print("  Dooray API 토큰을 입력하세요.")
    print("  (Dooray > 설정 > API 토큰에서 발급)")
    print("  형식: org_id:token (예: ajjt1imxmtj4:EXAMPLEtoken1234567890)")
    print()

    token = input("  API 토큰: ").strip()
    if not token:
        print("  [오류] 토큰이 비어있습니다.")
        return False

    # 테넌트 ID
    print()
    print("  테넌트 ID를 입력하세요.")
    print("  (Dooray URL에서 확인: https://XXXXX.dooray.com 의 테넌트 정보)")
    tenant_id = input("  테넌트 ID (기본: 1387695619080878080): ").strip()
    if not tenant_id:
        tenant_id = "1387695619080878080"

    # .env 작성
    env_content = f"""# Dooray API 인증 토큰
DOORAY_API_TOKEN={token}

# 테넌트 ID
DOORAY_TENANT_ID={tenant_id}

# 기본 프로젝트 ID (선택 - 나중에 설정 가능)
DOORAY_DEFAULT_PROJECT_ID=

# Dooray Messenger Webhook URL (선택)
DOORAY_WEBHOOK_URL=
"""
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(env_content)

    print(f"  -> .env 파일 생성 완료")
    return True


def step_2_deps():
    """의존성 설치"""
    print()
    print("[2/5] 의존성 설치")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q",
             "mcp[cli]", "requests", "python-dotenv"],
            check=True,
            capture_output=True,
        )
        print("  -> 설치 완료")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [오류] 설치 실패: {e.stderr.decode()[:200]}")
        return False


def step_3_verify():
    """연결 검증"""
    print()
    print("[3/5] Dooray API 연결 검증")

    # 환경변수 로드
    sys.path.insert(0, SCRIPT_DIR)
    from dotenv import load_dotenv
    load_dotenv(ENV_FILE, override=True)

    from src.client import DoorayClient
    from src.validators import ValidationError

    try:
        client = DoorayClient()
        print(f"  -> 클라이언트 초기화 OK (tenant: {client.tenant_id})")
    except ValidationError as e:
        print(f"  [오류] {e}")
        return None

    # 내 정보 확인
    my_id = client.get_my_member_id()
    if my_id:
        print(f"  -> 내 멤버 ID: {my_id}")
    else:
        print("  -> 내 정보 조회 불가 (일부 기능 제한될 수 있음)")

    return client


def step_4_discover(client):
    """프로젝트 자동 탐색"""
    print()
    print("[4/5] 프로젝트 자동 탐색")

    try:
        projects = client.discover_projects()
        active = [p for p in projects if p.get("state") != "deleted"]
        print(f"  -> {len(active)}개 프로젝트 발견")
        print()

        # projects.json 저장
        proj_dict = {}
        for i, p in enumerate(active):
            name = p.get("name", f"project_{i}")
            proj_dict[name] = {
                "id": p["id"],
                "description": p.get("description", "") or p.get("code", ""),
            }
            print(f"  {i+1:3d}. {name} ({p['id']})")

        with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
            json.dump(proj_dict, f, ensure_ascii=False, indent=2)

        print()
        print(f"  -> projects.json 저장 완료 ({len(proj_dict)}개)")

        # 기본 프로젝트 설정
        print()
        print("  기본 프로젝트를 설정하시겠습니까?")
        print("  (자주 쓰는 프로젝트 번호를 입력, 건너뛰려면 Enter)")
        choice = input("  번호: ").strip()
        if choice and choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(active):
                default_pid = active[idx]["id"]
                default_name = active[idx]["name"]
                # .env 업데이트
                _update_env("DOORAY_DEFAULT_PROJECT_ID", default_pid)
                print(f"  -> 기본 프로젝트 설정: {default_name} ({default_pid})")

        return True
    except Exception as e:
        print(f"  [오류] 프로젝트 탐색 실패: {e}")
        print("  프로젝트 탐색은 나중에 Claude에게 'dooray_discover_projects 실행해줘'로 할 수 있습니다.")
        return True  # 치명적이지 않음


def step_5_register():
    """Claude Code MCP 등록"""
    print()
    print("[5/5] Claude Code MCP 서버 등록")

    run_server = os.path.join(SCRIPT_DIR, "run_server.py").replace("\\", "/")

    try:
        # 기존 등록 제거 (있으면)
        subprocess.run(
            ["claude", "mcp", "remove", "dooray-mcp", "-s", "user"],
            capture_output=True,
        )
        # 새로 등록
        result = subprocess.run(
            ["claude", "mcp", "add", "dooray-mcp", "-s", "user",
             "--", "python", run_server],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("  -> MCP 서버 등록 완료!")
            print()
            print("  Claude Code를 새로 시작하면 바로 사용할 수 있습니다.")
            return True
        else:
            print(f"  [경고] 자동 등록 실패: {result.stderr[:200]}")
            print(f"  수동으로 등록하세요:")
            print(f'    claude mcp add dooray-mcp -s user -- python "{run_server}"')
            return True
    except FileNotFoundError:
        print("  [경고] claude CLI를 찾을 수 없습니다.")
        print(f"  Claude Code 설치 후 수동으로 등록하세요:")
        print(f'    claude mcp add dooray-mcp -s user -- python "{run_server}"')
        return True


def _update_env(key, value):
    """기존 .env 파일에서 특정 키 업데이트"""
    lines = []
    found = False
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        for line in lines:
            if line.strip().startswith(f"{key}="):
                f.write(f"{key}={value}\n")
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f"\n{key}={value}\n")


def main():
    print_header()

    if not step_1_token():
        return
    if not step_2_deps():
        return

    client = step_3_verify()
    if client is None:
        return

    step_4_discover(client)
    step_5_register()

    print()
    print("=" * 55)
    print("  설치 완료!")
    print("=" * 55)
    print()
    print("  사용법:")
    print("  1. Claude Code 새로 시작")
    print('  2. "파트너신청 프로젝트 태스크 보여줘" 입력')
    print('  3. "내 태스크 보여줘" 입력')
    print()


if __name__ == "__main__":
    main()
