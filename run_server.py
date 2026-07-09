"""Dooray MCP Server 실행 스크립트

Claude Code MCP 등록 시 이 파일을 사용합니다:
  claude mcp add dooray-mcp -s user -- python /path/to/dooray-mcp/run_server.py

자동 업데이트:
  서버 시작 시 git pull --ff-only를 시도하여 항상 최신 코드로 실행됩니다.
  - 네트워크 불가/로컬 수정 충돌 시에도 서버는 기존 코드로 정상 시작합니다.
  - 끄려면 .env 또는 환경변수에 DOORAY_MCP_AUTO_UPDATE=false 설정.
"""

import os
import subprocess
import sys

# dooray-mcp 루트를 sys.path에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# .env 로드를 위해 작업 디렉토리 변경
os.chdir(project_root)


def _auto_update() -> None:
    """서버 시작 전 git pull로 최신 코드 반영.

    주의: MCP는 stdout으로 통신하므로 로그는 반드시 stderr로만 출력한다.
    어떤 실패(git 없음, 오프라인, 충돌)도 서버 시작을 막지 않는다.
    """
    flag = os.environ.get("DOORAY_MCP_AUTO_UPDATE", "").strip().lower()
    if flag in ("false", "0", "no", "off"):
        return
    # .env의 설정도 존중 (dotenv 로드 전이므로 직접 파싱)
    env_file = os.path.join(project_root, ".env")
    if not flag and os.path.isfile(env_file):
        try:
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("DOORAY_MCP_AUTO_UPDATE"):
                        value = line.split("=", 1)[-1].strip().lower()
                        if value in ("false", "0", "no", "off"):
                            return
        except OSError:
            pass

    if not os.path.isdir(os.path.join(project_root, ".git")):
        return

    try:
        result = subprocess.run(
            ["git", "-C", project_root, "pull", "--ff-only", "--quiet"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            print("[dooray-mcp] 자동 업데이트 확인 완료 (최신 상태)", file=sys.stderr)
        else:
            print(
                f"[dooray-mcp] 자동 업데이트 건너뜀: {result.stderr.strip()[:200]}",
                file=sys.stderr,
            )
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"[dooray-mcp] 자동 업데이트 건너뜀 (오프라인?): {e}", file=sys.stderr)


if __name__ == "__main__":
    _auto_update()
    from src.server import main
    main()
