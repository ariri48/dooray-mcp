"""두레이 메신저 봇 서버

두레이 메신저에서:
  /내태스크        → 슬래시 명령 (무료)
  /주간보고        → 슬래시 명령 (무료)
  /ai 자연어질문   → Claude AI (유료)

실행:
  python bot/app.py
  → http://localhost:8585

두레이 봇 등록:
  두레이 > 설정 > 서비스/봇 연동 > 봇 추가
  → Outgoing Webhook URL: http://{서버IP}:8585/webhook
"""

from __future__ import annotations

import json
import os
import sys
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from flask import Flask, request, jsonify

from commands import execute_command
from ai_handler import handle_ai_request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("dooray-bot")

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    """헬스체크"""
    return jsonify({"status": "ok", "bot": "dooray-mcp"})


@app.route("/webhook", methods=["POST"])
def webhook():
    """두레이 메신저 Outgoing Webhook 핸들러.

    두레이가 보내는 형식:
    {
        "tenantId": "...",
        "tenantDomain": "...",
        "channelId": "...",
        "channelName": "...",
        "userId": "...",
        "command": "/명령어",
        "text": "나머지 텍스트",
        "responseUrl": "...",
        "triggerId": "..."
    }

    또는 일반 멘션:
    {
        "text": "@봇이름 메시지 내용",
        ...
    }
    """
    data = request.json or {}
    logger.info(f"Webhook 수신: {json.dumps(data, ensure_ascii=False)[:300]}")

    # 슬래시 명령어 처리
    command = data.get("command", "")
    text = data.get("text", "")

    # 방법 1: 두레이 Slash Command 형식
    if command:
        full_text = f"{command} {text}".strip()
        response_text = execute_command(full_text)
        if response_text:
            return jsonify({
                "text": response_text,
                "responseType": "inChannel",
            })

    # 방법 2: 일반 텍스트에서 / 명령어 추출
    message = text.strip()
    if message.startswith("/"):
        # /ai 명령어 → Claude AI
        if message.startswith("/ai "):
            ai_query = message[4:].strip()
            if ai_query:
                logger.info(f"AI 요청: {ai_query}")
                response_text = handle_ai_request(ai_query)
                return jsonify({
                    "text": response_text,
                    "responseType": "inChannel",
                })

        # 일반 슬래시 명령어
        response_text = execute_command(message)
        if response_text:
            return jsonify({
                "text": response_text,
                "responseType": "inChannel",
            })

        # 알 수 없는 명령어
        return jsonify({
            "text": f"알 수 없는 명령어입니다. `/도움말`로 사용 가능한 명령어를 확인하세요.",
            "responseType": "ephemeral",
        })

    # 방법 3: 멘션 또는 일반 메시지 → AI로 전달
    if message:
        # @봇이름 제거
        import re
        message = re.sub(r"^@\S+\s*", "", message).strip()
        if message:
            response_text = handle_ai_request(message)
            return jsonify({
                "text": response_text,
                "responseType": "inChannel",
            })

    return jsonify({"text": "메시지를 이해하지 못했습니다. `/도움말`을 입력하세요."})


@app.route("/command/<cmd_name>", methods=["POST"])
def slash_command(cmd_name: str):
    """두레이 개별 슬래시 명령어 엔드포인트.

    두레이에서 각 명령어별로 별도 URL을 등록할 수 있음:
    - /내태스크 → POST /command/내태스크
    - /주간보고 → POST /command/주간보고
    """
    data = request.json or {}
    text = data.get("text", "")

    full_text = f"/{cmd_name} {text}".strip()
    response_text = execute_command(full_text)

    if response_text:
        return jsonify({
            "text": response_text,
            "responseType": "inChannel",
        })

    return jsonify({"text": f"/{cmd_name} 처리 실패"})


if __name__ == "__main__":
    port = int(os.environ.get("BOT_PORT", "8585"))
    logger.info(f"Dooray MCP Bot 시작 (port: {port})")
    logger.info(f"  Webhook URL: http://localhost:{port}/webhook")
    logger.info(f"  AI 모드: {'활성' if os.environ.get('ANTHROPIC_API_KEY') else '비활성 (ANTHROPIC_API_KEY 미설정)'}")
    logger.info(f"  등록된 명령어: /도움말, /내태스크, /현황, /주간보고, /방치, /품질, /검색, /중복, /파이프라인")

    app.run(host="0.0.0.0", port=port, debug=False)
