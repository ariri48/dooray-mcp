"""Dooray MCP Server 실행 스크립트

Claude Code MCP 등록 시 이 파일을 사용합니다:
  claude mcp add dooray-mcp -s user -- python C:/Users/NHN/dooray-mcp/run_server.py
"""

import os
import sys

# dooray-mcp 루트를 sys.path에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# .env 로드를 위해 작업 디렉토리 변경
os.chdir(project_root)

from src.server import main

if __name__ == "__main__":
    main()
