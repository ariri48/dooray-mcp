"""Dooray 서비스별 MCP 툴 등록 패키지

서비스 API 문서(https://helpdesk.dooray.com/share/pages/9wWo-xwiR66BO5LGshgVTg/2939987647631384419)의
전체 엔드포인트를 서비스 단위 모듈로 나눠 등록합니다.
"""

from __future__ import annotations

from . import (
    calendar,
    common,
    contacts,
    drive,
    messenger,
    posts_extra,
    project_admin,
    reservation,
    wiki,
)

_MODULES = [
    common,
    project_admin,
    posts_extra,
    calendar,
    drive,
    wiki,
    messenger,
    reservation,
    contacts,
]


def register_all(mcp, get_client) -> None:
    """모든 서비스 모듈의 MCP 툴을 등록"""
    for module in _MODULES:
        module.register(mcp, get_client)
