"""Dooray API 클라이언트 — 검증 레이어 내장

모든 API 호출은:
1. 입력값 검증 (validators.py)
2. HTTP 요청
3. 응답 구조 검증
4. 데이터 정제 후 반환

보안:
- 토큰은 .env에서만 로드
- 요청 타임아웃 10초 기본
- Rate limit: 요청 간 0.2초 대기
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

from .validators import (
    ValidationError,
    validate_api_response,
    validate_body_content,
    validate_json_array,
    validate_pagination,
    validate_post_id,
    validate_project_id,
    validate_subject,
    validate_subjects_list,
    validate_tag_names,
    validate_task,
    validate_task_list,
)

# ── 거래처 등록 상수 ──────────────────────────────────────
PARTNER_REG_PROJECT = "2798508237975631580"       # 클라우드지원팀-지원업무요청
PARTNER_REG_ASSIGNEE = "4050525636315836644"      # 김난우
PARTNER_REG_CC = ["3319948852515358760", "2295105655829543733"]  # 김제홍, 황미현
PARTNER_REG_WORKFLOW = "3757305055271011304"       # 진행 중
PARTNER_REG_TAG = "거래처-신규등록"
PARTNER_SOURCE_PROJECT = "4118231653304784792"     # 파트너-신청-등록

PARTNER_REG_BODY_TEMPLATE = """- 거래처 구분
  - [x] 매출
  - [x] 매입
- 거래처명
  - {partner_name}
- 청구 기준 구분
  - [ ] 계약
    - 계정 정보:
    - 사업 기안 번호:
  - [x] NCA(사용량)
    - 계정 정보:
      {nca_info}
    - 청구 시작 월:
- 필요서류
  - 매출 : 사업자등록증, 개인정보(거래처 담당자정보) 수집/이용 동의서
  - 매입 : 사업자등록증, 개인정보(거래처 담당자정보) 수집/이용 동의서, 입금계좌신고서, 통장사본, 법인인감증명서(3개월이내발급본, 대표자주민번호 뒷자리는 가릴 것)

> 원본 태스크: dooray://1387695619080878080/tasks/{source_post_id}"""
from .projects import resolve_project_alias

# .env 로드 (dooray-mcp 루트 디렉토리에서)
_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(_env_path)


def _prompt_api_token_dialog() -> str:
    """API 토큰 입력 창 표시 (공용 PC용 — 파일 저장 없이 메모리에만 보관).

    .env에 DOORAY_API_TOKEN이 비어있을 때 첫 사용 시 호출됩니다.
    macOS 전용 (osascript). 취소하거나 GUI가 없으면 빈 문자열 반환.
    """
    import subprocess
    import sys as _sys

    if _sys.platform != "darwin":
        return ""

    script = (
        'set dlg to display dialog '
        '"Dooray API 토큰을 입력하세요 (형식: org_id:token)\n\n'
        '공용 PC 보호를 위해 토큰은 저장되지 않으며,\n'
        'Claude Code를 종료하면 사라집니다." '
        'default answer "" with hidden answer '
        'with title "Dooray MCP 인증" with icon caution\n'
        'text returned of dlg'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=180,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    if result.returncode != 0:  # 사용자가 취소
        return ""
    return result.stdout.strip()


class DoorayClient:
    """Dooray REST API 클라이언트 (검증 내장)"""

    API_ORIGIN = "https://api.dooray.com"
    BASE_URL = "https://api.dooray.com/project/v1"
    FILE_API_URL = "https://file-api.dooray.com"
    COMMON_API_URL = "https://api.dooray.com/common/v1"
    REQUEST_TIMEOUT = 10
    RATE_LIMIT_SLEEP = 0.2

    def __init__(self):
        self.api_token = os.environ.get("DOORAY_API_TOKEN", "")
        self.tenant_id = os.environ.get("DOORAY_TENANT_ID", "")
        self.default_project_id = os.environ.get("DOORAY_DEFAULT_PROJECT_ID", "")
        self.webhook_url = os.environ.get("DOORAY_WEBHOOK_URL", "")

        # 공용 PC 모드: .env에 토큰이 없으면 입력 창으로 요청 (메모리에만 보관)
        if not self.api_token:
            self.api_token = _prompt_api_token_dialog()

        if not self.api_token:
            raise ValidationError(
                "DOORAY_API_TOKEN이 설정되지 않았습니다. "
                "개인 PC라면 .env 파일에 토큰을 설정하고, "
                "공용 PC라면 다시 시도하여 입력 창에 토큰을 입력하세요. "
                "(Dooray > 설정 > API 토큰에서 발급)"
            )
        if not self.tenant_id:
            raise ValidationError(
                "DOORAY_TENANT_ID가 설정되지 않았습니다. "
                ".env 파일에 테넌트 ID를 설정하세요."
            )

        self._headers = {
            "Authorization": f"dooray-api {self.api_token}",
            "Content-Type": "application/json",
        }
        self._last_request_time = 0.0

    # ── 내부 HTTP 헬퍼 ────────────────────────────────────

    def _rate_limit(self):
        """요청 간 최소 간격 보장 (Dooray API 보호)"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_SLEEP:
            time.sleep(self.RATE_LIMIT_SLEEP - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str, params: dict | None = None, context: str = "") -> Any:
        self._rate_limit()
        try:
            resp = requests.get(
                url, headers=self._headers, params=params,
                timeout=self.REQUEST_TIMEOUT,
            )
        except requests.RequestException as e:
            raise ValidationError(f"[{context}] 네트워크 오류: {e}")

        if resp.status_code != 200:
            raise ValidationError(
                f"[{context}] HTTP {resp.status_code}: {resp.text[:300]}"
            )
        return validate_api_response(resp.json(), context)

    def _post(self, url: str, payload: dict, context: str = "") -> Any:
        self._rate_limit()
        try:
            resp = requests.post(
                url, headers=self._headers, json=payload,
                timeout=self.REQUEST_TIMEOUT,
            )
        except requests.RequestException as e:
            raise ValidationError(f"[{context}] 네트워크 오류: {e}")

        if resp.status_code != 200:
            raise ValidationError(
                f"[{context}] HTTP {resp.status_code}: {resp.text[:300]}"
            )
        return validate_api_response(resp.json(), context)

    def _put(self, url: str, payload: dict, context: str = "") -> Any:
        self._rate_limit()
        try:
            resp = requests.put(
                url, headers=self._headers, json=payload,
                timeout=self.REQUEST_TIMEOUT,
            )
        except requests.RequestException as e:
            raise ValidationError(f"[{context}] 네트워크 오류: {e}")

        if resp.status_code != 200:
            raise ValidationError(
                f"[{context}] HTTP {resp.status_code}: {resp.text[:300]}"
            )
        return validate_api_response(resp.json(), context)

    def _delete(self, url: str, context: str = "") -> Any:
        self._rate_limit()
        try:
            resp = requests.delete(
                url, headers=self._headers,
                timeout=self.REQUEST_TIMEOUT,
            )
        except requests.RequestException as e:
            raise ValidationError(f"[{context}] 네트워크 오류: {e}")

        if resp.status_code != 200:
            raise ValidationError(
                f"[{context}] HTTP {resp.status_code}: {resp.text[:300]}"
            )
        return validate_api_response(resp.json(), context)

    def _resolve_project(self, project_id: str | None) -> str:
        """프로젝트 ID 해석: 별칭("파트너신청") → 숫자 ID 자동 변환."""
        return resolve_project_alias(project_id, self.default_project_id)

    # ── 범용 API 레이어 (모든 Dooray 서비스: common/project/calendar/drive/wiki/messenger/reservation/contacts) ──

    def api(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        payload: Any = None,
        context: str = "",
        full: bool = False,
    ) -> Any:
        """https://api.dooray.com 하위 모든 서비스 API 호출.

        Args:
            method: GET / POST / PUT / DELETE
            path: "/calendar/v1/calendars" 형태의 절대 경로
            params: 쿼리 파라미터
            payload: JSON 바디 (dict 또는 list)
            full: True면 {"result": ..., "totalCount": ...} 반환 (목록 API용)

        Returns:
            API 응답의 result (full=True면 totalCount 포함 dict)
        """
        method = method.upper()
        if method not in ("GET", "POST", "PUT", "DELETE"):
            raise ValidationError(f"지원하지 않는 HTTP 메서드: {method}")
        if not path.startswith("/"):
            path = "/" + path

        ctx = context or f"{method} {path}"
        url = f"{self.API_ORIGIN}{path}"
        self._rate_limit()
        try:
            resp = requests.request(
                method, url,
                headers=self._headers,
                params=params,
                json=payload if payload is not None else None,
                timeout=self.REQUEST_TIMEOUT,
            )
        except requests.RequestException as e:
            raise ValidationError(f"[{ctx}] 네트워크 오류: {e}")

        if resp.status_code not in (200, 201, 204):
            raise ValidationError(f"[{ctx}] HTTP {resp.status_code}: {resp.text[:300]}")

        if not resp.content:
            return {"result": None, "totalCount": None} if full else None

        try:
            data = resp.json()
        except ValueError:
            raise ValidationError(f"[{ctx}] 응답이 JSON이 아닙니다: {resp.text[:200]}")

        result = validate_api_response(data, ctx)
        if full:
            return {"result": result, "totalCount": data.get("totalCount")}
        return result

    def api_upload(
        self,
        path: str,
        file_path: str,
        params: dict | None = None,
        context: str = "",
        max_size_mb: int = 100,
    ) -> Any:
        """multipart/form-data 파일 업로드 (Drive/Wiki/Draft 등).

        Returns:
            API 응답의 result (업로드된 파일 메타)
        """
        import os as _os

        if not _os.path.isfile(file_path):
            raise ValidationError(f"파일을 찾을 수 없습니다: {file_path}")
        file_size = _os.path.getsize(file_path)
        if file_size > max_size_mb * 1024 * 1024:
            raise ValidationError(
                f"파일 크기가 {max_size_mb}MB를 초과합니다: {file_size / 1024 / 1024:.1f}MB"
            )

        ctx = context or f"파일 업로드 {path}"
        url = f"{self.API_ORIGIN}{path}"
        self._rate_limit()
        try:
            with open(file_path, "rb") as f:
                resp = requests.post(
                    url,
                    headers={"Authorization": f"dooray-api {self.api_token}"},
                    params=params,
                    files={"file": (_os.path.basename(file_path), f)},
                    timeout=120,
                )
        except requests.RequestException as e:
            raise ValidationError(f"[{ctx}] 네트워크 오류: {e}")

        if resp.status_code not in (200, 201):
            raise ValidationError(f"[{ctx}] HTTP {resp.status_code}: {resp.text[:300]}")
        if not resp.content:
            return None
        try:
            return validate_api_response(resp.json(), ctx)
        except ValueError:
            return None

    def api_download(
        self,
        path: str,
        file_name: str,
        params: dict | None = None,
        context: str = "",
    ) -> str:
        """?media=raw 형태의 파일 다운로드 (200 직접 응답 / 307 리다이렉트 모두 처리).

        Returns:
            다운로드된 로컬 파일 경로
        """
        import tempfile
        import os as _os

        ctx = context or f"파일 다운로드 {path}"
        url = f"{self.API_ORIGIN}{path}"
        auth_header = {"Authorization": f"dooray-api {self.api_token}"}
        self._rate_limit()
        try:
            resp = requests.get(
                url, headers=auth_header, params=params,
                timeout=60, allow_redirects=False, stream=True,
            )
        except requests.RequestException as e:
            raise ValidationError(f"[{ctx}] 네트워크 오류: {e}")

        # 307 리다이렉트면 Location으로 재요청
        if resp.status_code in (301, 302, 307, 308) and "Location" in resp.headers:
            try:
                resp = requests.get(
                    resp.headers["Location"], headers=auth_header,
                    timeout=60, stream=True,
                )
            except requests.RequestException as e:
                raise ValidationError(f"[{ctx}] 리다이렉트 오류: {e}")

        if resp.status_code != 200:
            raise ValidationError(f"[{ctx}] HTTP {resp.status_code}: {resp.text[:300]}")

        tmp_dir = tempfile.mkdtemp(prefix="dooray_")
        local_path = _os.path.join(tmp_dir, file_name)
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return local_path

    # ── Phase 1: 핵심 CRUD ────────────────────────────────

    def list_tasks(
        self,
        project_id: str | None = None,
        page: int = 0,
        size: int = 100,
        keyword: str | None = None,
    ) -> dict:
        """태스크 목록 조회 (페이지네이션 + 키워드 검색).

        Args:
            keyword: 제목 검색 키워드 (지정 시 전체 태스크에서 필터링)

        Returns:
            {"tasks": [...], "totalCount": int, "page": int, "size": int}
        """
        pid = self._resolve_project(project_id)

        # 키워드 검색: 전체 태스크를 수집 후 필터링
        if keyword and keyword.strip():
            keyword = keyword.strip().lower()
            all_tasks = self.list_all_tasks(pid)
            matched = [
                t for t in all_tasks
                if keyword in t.get("subject", "").lower()
            ]
            # 키워드 검색 결과에 페이지네이션 적용
            page, size = validate_pagination(page, size)
            start = page * size
            end = start + size
            paged = matched[start:end]
            return {
                "tasks": paged,
                "totalCount": len(matched),
                "page": page,
                "size": size,
                "keyword": keyword,
            }

        page, size = validate_pagination(page, size)

        url = f"{self.BASE_URL}/projects/{pid}/posts"
        result = self._get(url, {"page": page, "size": size}, "태스크 목록 조회")

        # result가 리스트인 경우 (posts 배열)
        if isinstance(result, list):
            tasks = validate_task_list(result)
            return {"tasks": tasks, "totalCount": len(tasks), "page": page, "size": size}

        # 일반적인 Dooray 응답 — result 자체가 리스트
        tasks = validate_task_list(result if isinstance(result, list) else [])
        return {"tasks": tasks, "totalCount": len(tasks), "page": page, "size": size}

    def list_all_tasks(self, project_id: str | None = None) -> list[dict]:
        """프로젝트의 모든 태스크를 페이지네이션으로 수집.

        Returns:
            전체 태스크 리스트 (중복 제거, 검증 완료)
        """
        pid = self._resolve_project(project_id)
        all_tasks = []
        seen_ids = set()
        page = 0

        while True:
            url = f"{self.BASE_URL}/projects/{pid}/posts"
            # _get 내에서 validate_api_response 호출
            raw = self._get(
                url, {"page": page, "size": 100}, f"전체 태스크 수집 (p{page})"
            )

            items = raw if isinstance(raw, list) else []
            if not items:
                break

            for t in items:
                tid = t.get("id", "")
                if tid and tid not in seen_ids:
                    seen_ids.add(tid)
                    all_tasks.append(t)

            if len(items) < 100:
                break
            page += 1

        return validate_task_list(all_tasks)

    def get_task(self, post_id: str, project_id: str | None = None) -> dict:
        """단일 태스크 상세 조회 (첨부파일 포함).

        Returns:
            검증된 태스크 dict (본문, 첨부파일 포함)
        """
        pid = self._resolve_project(project_id)
        post_id = validate_post_id(post_id)

        url = f"{self.BASE_URL}/projects/{pid}/posts/{post_id}"
        result = self._get(url, context=f"태스크 조회 ({post_id})")
        task = validate_task(result, require_body=False)

        # 첨부파일 목록 조회
        try:
            files = self.get_task_files(post_id, pid)
            task["_files"] = files
        except Exception:
            task["_files"] = []

        return task

    def get_task_files(self, post_id: str, project_id: str | None = None) -> list[dict]:
        """태스크 첨부파일 목록 조회.

        Returns:
            [{"id": "...", "name": "...", "size": int, "createdAt": "..."}, ...]
        """
        pid = self._resolve_project(project_id)
        post_id = validate_post_id(post_id)

        url = f"{self.BASE_URL}/projects/{pid}/posts/{post_id}/files"
        try:
            result = self._get(url, context=f"첨부파일 조회 ({post_id})")
        except ValidationError:
            return []

        files = result if isinstance(result, list) else []
        return [
            {
                "id": f.get("id", ""),
                "name": f.get("name", ""),
                "size": f.get("size", 0),
                "createdAt": f.get("createdAt", ""),
            }
            for f in files
        ]

    def create_task(
        self,
        subject: str,
        body_md: str = "",
        project_id: str | None = None,
        tag_names: list[str] | None = None,
        parent_post_id: str | None = None,
        workflow_id: str | None = None,
        milestone_id: str | None = None,
        assignee_ids: list[str] | None = None,
        cc_ids: list[str] | None = None,
        due_date: str | None = None,
        priority: str = "none",
    ) -> dict:
        """태스크 생성.

        Returns:
            {"id": "...", "subject": "...", "link": "dooray://..."} 생성 결과
        """
        pid = self._resolve_project(project_id)
        subject = validate_subject(subject)

        payload: dict[str, Any] = {
            "subject": subject,
            "body": {
                "mimeType": "text/x-markdown",
                "content": body_md or "",
            },
            "priority": priority,
        }

        # 태그 이름 → ID 해석
        if tag_names:
            tag_names = validate_tag_names(tag_names)
            tag_ids = self._resolve_tag_ids(pid, tag_names)
            if tag_ids:
                payload["tagIdList"] = tag_ids

        if parent_post_id:
            payload["parentPostId"] = validate_post_id(parent_post_id, "parentPostId")
        if workflow_id:
            payload["workflowId"] = workflow_id
        if milestone_id:
            payload["milestoneId"] = milestone_id
        if due_date:
            payload["dueDate"] = due_date

        if assignee_ids or cc_ids:
            users = {}
            if assignee_ids:
                users["to"] = [
                    {"type": "member", "member": {"organizationMemberId": mid}}
                    for mid in assignee_ids
                ]
            if cc_ids:
                users["cc"] = [
                    {"type": "member", "member": {"organizationMemberId": mid}}
                    for mid in cc_ids
                ]
            payload["users"] = users

        url = f"{self.BASE_URL}/projects/{pid}/posts"
        result = self._post(url, payload, "태스크 생성")

        created_id = result.get("id", "") if isinstance(result, dict) else ""
        return {
            "id": created_id,
            "subject": subject,
            "link": self.task_link(created_id),
            "message": f"태스크 생성 완료: '{subject}'",
        }

    def update_task(
        self,
        post_id: str,
        project_id: str | None = None,
        subject: str | None = None,
        body_md: str | None = None,
        workflow_id: str | None = None,
        milestone_id: str | None = None,
        tag_names: list[str] | None = None,
        assignee_ids: list[str] | None = None,
        cc_ids: list[str] | None = None,
    ) -> dict:
        """태스크 수정 (변경된 필드만 전송).

        Returns:
            {"id": "...", "변경사항": [...], "link": "dooray://..."} 변경 요약
        """
        pid = self._resolve_project(project_id)
        post_id = validate_post_id(post_id)

        payload: dict[str, Any] = {}
        changes = []

        if subject is not None:
            payload["subject"] = validate_subject(subject)
            changes.append(f"제목 변경 → {subject}")

        if body_md is not None:
            payload["body"] = {
                "mimeType": "text/x-markdown",
                "content": body_md,
            }
            changes.append("본문 수정")

        if workflow_id:
            payload["workflowId"] = workflow_id
            changes.append(f"워크플로우 변경 → {workflow_id}")

        if milestone_id:
            payload["milestoneId"] = milestone_id
            changes.append(f"마일스톤 변경 → {milestone_id}")

        if tag_names is not None:
            tag_names = validate_tag_names(tag_names)
            tag_ids = self._resolve_tag_ids(pid, tag_names)
            payload["tagIdList"] = tag_ids
            changes.append(f"태그 변경 → {tag_names}")

        # 담당자 변경
        if assignee_ids is not None:
            to_list = [
                {"type": "member", "member": {"organizationMemberId": mid}}
                for mid in assignee_ids
            ]
            if "users" not in payload:
                payload["users"] = {}
            payload["users"]["to"] = to_list
            changes.append(f"담당자 변경 → {assignee_ids}")

        # 참조자 변경
        if cc_ids is not None:
            cc_list = [
                {"type": "member", "member": {"organizationMemberId": mid}}
                for mid in cc_ids
            ]
            if "users" not in payload:
                payload["users"] = {}
            payload["users"]["cc"] = cc_list
            changes.append(f"참조자 변경 → {cc_ids}")

        if not payload:
            raise ValidationError("변경할 내용이 없습니다. 최소 하나의 필드를 지정하세요.")

        url = f"{self.BASE_URL}/projects/{pid}/posts/{post_id}"
        self._put(url, payload, f"태스크 수정 ({post_id})")

        return {
            "id": post_id,
            "변경사항": changes,
            "link": self.task_link(post_id),
            "message": f"태스크 수정 완료 ({len(changes)}건 변경)",
        }

    def add_comment(
        self,
        post_id: str,
        content_md: str,
        project_id: str | None = None,
    ) -> dict:
        """태스크에 마크다운 코멘트 추가.

        Returns:
            {"post_id": "...", "message": "..."} 결과
        """
        pid = self._resolve_project(project_id)
        post_id = validate_post_id(post_id)
        content_md = validate_body_content(content_md)

        url = f"{self.BASE_URL}/projects/{pid}/posts/{post_id}/logs"
        payload = {
            "body": {"mimeType": "text/x-markdown", "content": content_md},
        }
        self._post(url, payload, f"코멘트 추가 ({post_id})")

        return {
            "post_id": post_id,
            "link": self.task_link(post_id),
            "message": "코멘트 등록 완료",
        }

    def list_tags(self, project_id: str | None = None) -> list[dict]:
        """프로젝트 태그 목록 조회.

        Returns:
            [{"id": "...", "name": "..."}, ...]
        """
        pid = self._resolve_project(project_id)
        url = f"{self.BASE_URL}/projects/{pid}/tags"
        result = self._get(url, context="태그 목록 조회")
        tags = result if isinstance(result, list) else []
        return [{"id": t.get("id", ""), "name": t.get("name", "")} for t in tags]

    def list_members(self, project_id: str | None = None) -> list[dict]:
        """프로젝트 멤버 목록 조회.

        Returns:
            [{"id": "...", "name": "...", "email": "..."}, ...]
        """
        pid = self._resolve_project(project_id)
        url = f"{self.BASE_URL}/projects/{pid}/members"
        result = self._get(url, {"size": 100}, "멤버 목록 조회")
        members = result if isinstance(result, list) else []
        cleaned = []
        for m in members:
            member_id = m.get("organizationMemberId", "")
            org_member = m.get("organizationMember", {})
            # 이름: organizationMember.name → member.name 순으로 탐색
            name = (
                org_member.get("name", "")
                or m.get("member", {}).get("name", "")
                or m.get("name", "")
            )
            # 이메일: organizationMember.emailAddress → member.emailAddress
            email = (
                org_member.get("emailAddress", "")
                or m.get("member", {}).get("emailAddress", "")
                or m.get("emailAddress", "")
            )
            # 이름이 비어있으면 Common API로 개별 조회 시도
            if not name and member_id:
                name = self._get_member_name(member_id)
            cleaned.append({
                "id": member_id,
                "name": name,
                "email": email,
            })
        return cleaned

    def _get_member_name(self, member_id: str) -> str:
        """Common API에서 멤버 이름 조회 (fallback)."""
        try:
            url = f"{self.COMMON_API_URL}/members/{member_id}"
            result = self._get(url, context=f"멤버 조회 ({member_id})")
            if isinstance(result, dict):
                return result.get("name", "") or result.get("externalEmailAddress", "")
        except Exception:
            pass
        return ""

    # ── Phase 2: 업무 자동화 ──────────────────────────────

    def move_task(
        self,
        post_id: str,
        parent_post_id: str,
        project_id: str | None = None,
    ) -> dict:
        """태스크를 다른 상위 태스크 아래로 이동.

        [주의] 이 작업은 태스크의 위치를 변경합니다.
        """
        pid = self._resolve_project(project_id)
        post_id = validate_post_id(post_id)
        parent_post_id = validate_post_id(parent_post_id, "parent_post_id")

        url = f"{self.BASE_URL}/projects/{pid}/posts/{post_id}/move"
        payload = {"parentPostId": parent_post_id, "projectId": pid}
        self._post(url, payload, f"태스크 이동 ({post_id})")

        return {
            "post_id": post_id,
            "parent_post_id": parent_post_id,
            "message": f"태스크 이동 완료 → 상위 태스크 {parent_post_id}",
        }

    def download_file(
        self,
        post_id: str,
        file_id: str,
        file_name: str,
        project_id: str | None = None,
    ) -> str:
        """태스크 첨부파일을 임시 디렉토리에 다운로드.

        ?media=raw + 307 리다이렉트 패턴 사용.

        Returns:
            다운로드된 로컬 파일 경로
        """
        import tempfile
        import os as _os

        pid = self._resolve_project(project_id)
        post_id = validate_post_id(post_id)

        url = (
            f"{self.BASE_URL}/projects/{pid}/posts/{post_id}"
            f"/files/{file_id}?media=raw"
        )
        auth_header = {"Authorization": f"dooray-api {self.api_token}"}
        self._rate_limit()
        try:
            # Step 1: 307 리다이렉트 받기
            resp = requests.get(
                url,
                headers=auth_header,
                timeout=60,
                allow_redirects=False,
            )
        except requests.RequestException as e:
            raise ValidationError(f"[파일 다운로드] 네트워크 오류: {e}")

        if resp.status_code != 307 or "Location" not in resp.headers:
            raise ValidationError(
                f"[파일 다운로드] HTTP {resp.status_code}: {resp.text[:300]}"
            )

        # Step 2: 리다이렉트 URL로 재요청 (Authorization 포함)
        try:
            resp2 = requests.get(
                resp.headers["Location"],
                headers=auth_header,
                timeout=60,
                stream=True,
            )
        except requests.RequestException as e:
            raise ValidationError(f"[파일 다운로드] 리다이렉트 오류: {e}")

        if resp2.status_code != 200:
            raise ValidationError(
                f"[파일 다운로드] HTTP {resp2.status_code}: {resp2.text[:300]}"
            )

        # 임시 디렉토리에 저장
        tmp_dir = tempfile.mkdtemp(prefix="dooray_")
        local_path = _os.path.join(tmp_dir, file_name)
        with open(local_path, "wb") as f:
            for chunk in resp2.iter_content(chunk_size=8192):
                f.write(chunk)

        return local_path

    def copy_files_between_tasks(
        self,
        source_post_id: str,
        target_post_id: str,
        source_project_id: str | None = None,
        target_project_id: str | None = None,
        file_ids: list[str] | None = None,
    ) -> dict:
        """소스 태스크의 첨부파일을 타겟 태스크로 복사.

        Args:
            source_post_id: 원본 태스크 ID
            target_post_id: 대상 태스크 ID
            source_project_id: 원본 프로젝트 ID
            target_project_id: 대상 프로젝트 ID
            file_ids: 복사할 파일 ID 목록 (미지정 시 전체)

        Returns:
            복사 결과 요약
        """
        import os as _os

        # 원본 파일 목록 조회
        source_files = self.get_task_files(source_post_id, source_project_id)
        if not source_files:
            raise ValidationError("원본 태스크에 첨부파일이 없습니다.")

        # 특정 파일만 선택
        if file_ids:
            source_files = [f for f in source_files if f["id"] in file_ids]
            if not source_files:
                raise ValidationError("지정한 파일 ID에 해당하는 첨부파일이 없습니다.")

        copied = []
        errors = []
        for file_info in source_files:
            try:
                # 다운로드
                local_path = self.download_file(
                    post_id=source_post_id,
                    file_id=file_info["id"],
                    file_name=file_info["name"],
                    project_id=source_project_id,
                )
                # 업로드
                self.upload_file(
                    post_id=target_post_id,
                    file_path=local_path,
                    project_id=target_project_id,
                )
                copied.append(file_info["name"])
                # 임시 파일 삭제
                try:
                    _os.remove(local_path)
                    _os.rmdir(_os.path.dirname(local_path))
                except OSError:
                    pass
            except Exception as e:
                errors.append(f"{file_info['name']}: {e}")

        result = {
            "복사_성공": copied,
            "복사_실패": errors,
            "message": f"파일 복사 완료: {len(copied)}건 성공, {len(errors)}건 실패",
        }
        return result

    def upload_file(
        self,
        post_id: str,
        file_path: str,
        project_id: str | None = None,
    ) -> dict:
        """태스크에 파일 첨부.

        Args:
            file_path: 업로드할 로컬 파일 경로
        """
        import os as _os

        pid = self._resolve_project(project_id)
        post_id = validate_post_id(post_id)

        if not _os.path.isfile(file_path):
            raise ValidationError(f"파일을 찾을 수 없습니다: {file_path}")

        file_size = _os.path.getsize(file_path)
        if file_size > 50 * 1024 * 1024:  # 50MB
            raise ValidationError(
                f"파일 크기가 50MB를 초과합니다: {file_size / 1024 / 1024:.1f}MB"
            )

        url = (
            f"{self.FILE_API_URL}/uploads/project/v1"
            f"/projects/{pid}/posts/{post_id}/files"
        )
        self._rate_limit()
        try:
            with open(file_path, "rb") as f:
                resp = requests.post(
                    url,
                    headers={"Authorization": f"dooray-api {self.api_token}"},
                    files={"file": f},
                    timeout=60,
                )
        except requests.RequestException as e:
            raise ValidationError(f"[파일 업로드] 네트워크 오류: {e}")

        if resp.status_code != 200:
            raise ValidationError(
                f"[파일 업로드] HTTP {resp.status_code}: {resp.text[:300]}"
            )

        return {
            "post_id": post_id,
            "file": _os.path.basename(file_path),
            "message": f"파일 첨부 완료: {_os.path.basename(file_path)}",
        }

    def list_workflows(self, project_id: str | None = None) -> list[dict]:
        """프로젝트 워크플로우(상태) 목록 조회."""
        pid = self._resolve_project(project_id)
        url = f"{self.BASE_URL}/projects/{pid}/workflows"
        result = self._get(url, context="워크플로우 목록 조회")
        workflows = result if isinstance(result, list) else []
        cleaned = []
        for wf in workflows:
            for status in wf.get("workflowStatusList", [wf]):
                cleaned.append({
                    "id": status.get("id", wf.get("id", "")),
                    "name": status.get("name", wf.get("name", "")),
                    "class": status.get("workflowClass", ""),
                })
        return cleaned

    def list_milestones(self, project_id: str | None = None) -> list[dict]:
        """프로젝트 마일스톤 목록 조회."""
        pid = self._resolve_project(project_id)
        url = f"{self.BASE_URL}/projects/{pid}/milestones"
        result = self._get(url, context="마일스톤 목록 조회")
        milestones = result if isinstance(result, list) else []
        return [
            {
                "id": ms.get("id", ""),
                "name": ms.get("name", ""),
                "status": ms.get("status", ""),
            }
            for ms in milestones
        ]

    def get_comments(
        self,
        post_id: str,
        project_id: str | None = None,
        page: int = 0,
        size: int = 100,
    ) -> list[dict]:
        """태스크 코멘트/로그 조회."""
        pid = self._resolve_project(project_id)
        post_id = validate_post_id(post_id)
        page, size = validate_pagination(page, size)

        url = f"{self.BASE_URL}/projects/{pid}/posts/{post_id}/logs"
        result = self._get(
            url,
            {"type": "comment", "page": page, "size": size},
            f"코멘트 조회 ({post_id})",
        )
        comments = result if isinstance(result, list) else []
        return [
            {
                "id": c.get("id", ""),
                "author": (
                    c.get("creator", {})
                    .get("member", {})
                    .get("name", "알 수 없음")
                ),
                "content": c.get("body", {}).get("content", ""),
                "createdAt": c.get("createdAt", ""),
            }
            for c in comments
        ]

    def delete_task(
        self,
        post_id: str,
        project_id: str | None = None,
    ) -> dict:
        """태스크 삭제.

        [주의] 이 작업은 되돌릴 수 없습니다!
        삭제 전 태스크 정보를 확인하고 반환합니다.
        """
        pid = self._resolve_project(project_id)
        post_id = validate_post_id(post_id)

        # 삭제 전 태스크 정보 조회 (확인용)
        task_info = self.get_task(post_id, pid)
        subject = task_info.get("subject", "(제목 없음)")

        url = f"{self.BASE_URL}/projects/{pid}/posts/{post_id}"
        self._delete(url, f"태스크 삭제 ({post_id})")

        return {
            "id": post_id,
            "삭제된_태스크": subject,
            "message": f"태스크 삭제 완료: '{subject}' ({post_id})",
            "warning": "이 작업은 되돌릴 수 없습니다.",
        }

    def send_webhook(self, message: str, bot_name: str = "Dooray MCP") -> dict:
        """Dooray Messenger Incoming Webhook으로 알림 발송."""
        if not self.webhook_url:
            raise ValidationError(
                "DOORAY_WEBHOOK_URL이 설정되지 않았습니다. "
                ".env 파일에 Webhook URL을 설정하세요."
            )
        if not message or not message.strip():
            raise ValidationError("메시지 내용이 비어있습니다.")

        payload = {"botName": bot_name, "text": message.strip()}
        self._rate_limit()
        try:
            resp = requests.post(
                self.webhook_url, json=payload, timeout=self.REQUEST_TIMEOUT
            )
        except requests.RequestException as e:
            raise ValidationError(f"[Webhook] 네트워크 오류: {e}")

        if resp.status_code != 200:
            raise ValidationError(
                f"[Webhook] HTTP {resp.status_code}: {resp.text[:300]}"
            )
        return {"message": "Webhook 발송 완료"}

    # ── 유틸리티 ──────────────────────────────────────────

    def task_link(self, post_id: str) -> str:
        """dooray:// 업무 참조 링크 반환"""
        return f"dooray://{self.tenant_id}/tasks/{post_id}"

    def _resolve_tag_ids(
        self, project_id: str, tag_names: list[str]
    ) -> list[str]:
        """태그 이름 → ID 변환. 없는 태그는 경고 포함하여 건너뜀."""
        if not tag_names:
            return []
        all_tags = self.list_tags(project_id)
        name_to_id = {t["name"]: t["id"] for t in all_tags}
        resolved = []
        for name in tag_names:
            if name in name_to_id:
                resolved.append(name_to_id[name])
            else:
                # 존재하지 않는 태그 → 무시하되 사용자에게 알림
                pass
        return resolved

    def mention(self, member_name: str, member_id: str) -> str:
        """Dooray @멘션 마크다운 생성"""
        return (
            f"[@{member_name}]"
            f'(dooray://{self.tenant_id}/members/{member_id} "member")'
        )

    # ── 팀 확장: 프로젝트 탐색 / 내 태스크 ────────────────

    def discover_projects(self) -> list[dict]:
        """현재 사용자가 접근 가능한 Dooray 프로젝트 목록을 API로 탐색.

        Returns:
            [{"id": "...", "name": "...", "code": "...", "description": "..."}, ...]
        """
        url = f"{self.BASE_URL}/projects"
        page = 0
        all_projects = []

        while True:
            result = self._get(
                url, {"page": page, "size": 100}, f"프로젝트 탐색 (p{page})"
            )
            items = result if isinstance(result, list) else []
            if not items:
                break
            for p in items:
                # Dooray API: code가 실제 프로젝트 표시명, name은 빈값
                display_name = p.get("code", "") or p.get("name", "")
                all_projects.append({
                    "id": p.get("id", ""),
                    "name": display_name,
                    "code": p.get("code", ""),
                    "description": p.get("description", ""),
                    "state": p.get("state", ""),
                    "scope": p.get("scope", ""),
                })
            if len(items) < 100:
                break
            page += 1

        return all_projects

    def get_my_member_id(self) -> str | None:
        """현재 API 토큰 소유자의 멤버 ID를 추정.

        Common API /members/me 호출로 확인.
        """
        try:
            url = f"{self.COMMON_API_URL}/members/me"
            result = self._get(url, context="내 정보 조회")
            if isinstance(result, dict):
                return result.get("id", "") or result.get("organizationMemberId", "")
        except Exception:
            pass
        return None

    def list_my_tasks(self, project_id: str | None = None) -> list[dict]:
        """현재 사용자에게 배정된 태스크만 필터링.

        API 토큰 소유자의 멤버 ID로 담당자 필터링.
        """
        my_id = self.get_my_member_id()
        if not my_id:
            raise ValidationError(
                "내 멤버 ID를 확인할 수 없습니다. "
                "API 토큰이 개인 토큰인지 확인하세요."
            )

        all_tasks = self.list_all_tasks(project_id)
        my_tasks = []
        for t in all_tasks:
            users = t.get("users", {})
            to_list = users.get("to", [])
            for u in to_list:
                member = u.get("member", {})
                member_id = member.get("organizationMemberId", "")
                if member_id == my_id:
                    my_tasks.append(t)
                    break

        return my_tasks

    # ── Phase 5: 추가 기능 ────────────────────────────────

    def create_subtasks(
        self,
        parent_post_id: str,
        subjects: list[str],
        project_id: str | None = None,
        workflow_id: str | None = None,
        assignee_ids: list[str] | None = None,
    ) -> dict:
        """상위 태스크 아래에 하위 태스크를 일괄 생성."""
        parent_post_id = validate_post_id(parent_post_id, "parent_post_id")
        created = []
        errors = []
        for subj in subjects:
            try:
                result = self.create_task(
                    subject=subj,
                    parent_post_id=parent_post_id,
                    project_id=project_id,
                    workflow_id=workflow_id,
                    assignee_ids=assignee_ids,
                )
                created.append({"subject": subj, "id": result["id"]})
            except Exception as e:
                errors.append({"subject": subj, "error": str(e)})
        return {
            "parent_post_id": parent_post_id,
            "생성_성공": created,
            "생성_실패": errors,
            "message": f"하위 태스크 생성: {len(created)}건 성공, {len(errors)}건 실패",
        }

    def bulk_create_tasks(
        self,
        tasks: list[dict],
        project_id: str | None = None,
    ) -> dict:
        """태스크를 일괄 생성. 각 dict에 subject(필수), body_md, tag_names, workflow_id, assignee_ids 가능."""
        created = []
        errors = []
        for i, task_def in enumerate(tasks):
            subj = task_def.get("subject", "")
            if not subj:
                errors.append({"index": i, "error": "subject 누락"})
                continue
            try:
                result = self.create_task(
                    subject=subj,
                    body_md=task_def.get("body_md", ""),
                    project_id=project_id,
                    tag_names=task_def.get("tag_names"),
                    workflow_id=task_def.get("workflow_id"),
                    assignee_ids=task_def.get("assignee_ids"),
                )
                created.append({"subject": subj, "id": result["id"], "link": result["link"]})
            except Exception as e:
                errors.append({"index": i, "subject": subj, "error": str(e)})
        return {
            "생성_성공": created,
            "생성_실패": errors,
            "message": f"일괄 생성: {len(created)}건 성공, {len(errors)}건 실패",
        }

    def list_templates(self, project_id: str | None = None) -> list[dict]:
        """프로젝트 템플릿 목록 조회."""
        pid = self._resolve_project(project_id)
        url = f"{self.BASE_URL}/projects/{pid}/templates"
        try:
            result = self._get(url, context="템플릿 목록 조회")
        except ValidationError:
            return []
        templates = result if isinstance(result, list) else []
        return [
            {
                "id": t.get("id", ""),
                "name": t.get("name", "") or t.get("subject", ""),
                "body": t.get("body", {}).get("content", ""),
            }
            for t in templates
        ]

    def batch_update_tasks(
        self,
        post_ids: list[str],
        project_id: str | None = None,
        workflow_id: str | None = None,
        milestone_id: str | None = None,
        tag_names: list[str] | None = None,
    ) -> dict:
        """여러 태스크를 동일한 조건으로 일괄 수정."""
        success = []
        errors = []
        for pid_str in post_ids:
            try:
                result = self.update_task(
                    post_id=pid_str,
                    project_id=project_id,
                    workflow_id=workflow_id,
                    milestone_id=milestone_id,
                    tag_names=tag_names,
                )
                success.append({"post_id": pid_str, "변경사항": result["변경사항"]})
            except Exception as e:
                errors.append({"post_id": pid_str, "error": str(e)})
        return {
            "성공": success,
            "실패": errors,
            "message": f"일괄 수정: {len(success)}건 성공, {len(errors)}건 실패",
        }

    def clone_task(
        self,
        source_post_id: str,
        source_project_id: str | None = None,
        target_project_id: str | None = None,
        new_subject: str | None = None,
        copy_attachments: bool = True,
    ) -> dict:
        """태스크를 복제 (제목, 본문, 태그, 첨부파일)."""
        task = self.get_task(source_post_id, source_project_id)
        subject = new_subject or f"[복사] {task.get('subject', '')}"
        body_content = task.get("body", {}).get("content", "")

        # 태그 이름 추출
        tag_names = [t.get("name", "") for t in task.get("tags", []) if t.get("name")]

        # 담당자 추출
        assignee_ids = []
        for u in task.get("users", {}).get("to", []):
            mid = u.get("member", {}).get("organizationMemberId", "")
            if mid:
                assignee_ids.append(mid)

        # 대상 프로젝트 결정
        tgt_pid = target_project_id or source_project_id

        result = self.create_task(
            subject=subject,
            body_md=body_content,
            project_id=tgt_pid,
            tag_names=tag_names if tag_names else None,
            assignee_ids=assignee_ids if assignee_ids else None,
        )

        # 첨부파일 복사
        file_result = None
        if copy_attachments and task.get("_files"):
            try:
                file_result = self.copy_files_between_tasks(
                    source_post_id=source_post_id,
                    target_post_id=result["id"],
                    source_project_id=source_project_id,
                    target_project_id=tgt_pid,
                )
            except Exception as e:
                file_result = {"error": str(e)}

        return {
            "원본_id": source_post_id,
            "새_태스크_id": result["id"],
            "제목": subject,
            "link": result["link"],
            "첨부파일_복사": file_result,
            "message": f"태스크 복제 완료: '{subject}'",
        }

    def _extract_nca_info(self, body_content: str) -> str:
        """태스크 본문에서 NCA 계정 정보를 추출."""
        import re as _re
        # 이메일 패턴 매칭
        emails = _re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', body_content)
        if emails:
            return emails[0]
        return ""

    def register_partner(
        self,
        source_post_id: str,
        source_project_id: str | None = None,
        partner_name: str | None = None,
        skip_file_copy: bool = False,
    ) -> dict:
        """파트너 태스크에서 거래처 등록 태스크를 자동 생성.

        1. 원본 태스크 조회 → 파트너명/NCA 정보 추출
        2. 클라우드지원팀 프로젝트에 거래처 등록 태스크 생성
        3. 담당자/참조자 지정
        4. 첨부파일 복사 (선택)
        """
        src_pid = source_project_id or PARTNER_SOURCE_PROJECT
        task = self.get_task(source_post_id, src_pid)

        # 파트너명 추출
        if not partner_name:
            subject = task.get("subject", "")
            # "2026/03/05 - 클라비" → "클라비"
            if " - " in subject:
                partner_name = subject.split(" - ", 1)[1].strip()
            else:
                partner_name = subject.strip()

        # NCA 정보 추출
        body_content = task.get("body", {}).get("content", "")
        nca_info = self._extract_nca_info(body_content) or ""

        # 거래처 등록 태스크 생성
        body_md = PARTNER_REG_BODY_TEMPLATE.format(
            partner_name=partner_name,
            nca_info=nca_info,
            source_post_id=source_post_id,
        )

        result = self.create_task(
            subject=f"[거래처 신규 등록] {partner_name}",
            body_md=body_md,
            project_id=PARTNER_REG_PROJECT,
            tag_names=[PARTNER_REG_TAG],
            workflow_id=PARTNER_REG_WORKFLOW,
            assignee_ids=[PARTNER_REG_ASSIGNEE],
            cc_ids=PARTNER_REG_CC,
        )

        new_post_id = result["id"]

        # 첨부파일 복사 (거래처 등록용 4종 자동 선별)
        file_result = None
        if not skip_file_copy and task.get("_files"):
            # 거래처 등록용 파일 패턴: 사업자등록증, 거래처등록안내문, 인감증명, 통장사본
            reg_patterns = ["사업자등록증", "거래처", "인감", "통장"]
            target_files = []
            for f in task["_files"]:
                fname = f.get("name", "")
                if any(p in fname for p in reg_patterns):
                    target_files.append(f["id"])

            if target_files:
                try:
                    file_result = self.copy_files_between_tasks(
                        source_post_id=source_post_id,
                        target_post_id=new_post_id,
                        source_project_id=src_pid,
                        target_project_id=PARTNER_REG_PROJECT,
                        file_ids=target_files,
                    )
                except Exception as e:
                    file_result = {"error": str(e), "안내": "첨부파일 복사 실패 — 수동 업로드 필요"}
            else:
                file_result = {"안내": "거래처 등록용 파일 패턴 미매칭 — 수동 확인 필요"}

        return {
            "원본_태스크": source_post_id,
            "파트너명": partner_name,
            "거래처등록_태스크": new_post_id,
            "link": result["link"],
            "담당자": "김난우",
            "참조": "김제홍, 황미현",
            "첨부파일": file_result,
            "message": f"거래처 등록 태스크 생성 완료: [거래처 신규 등록] {partner_name}",
        }

    def get_partner_pipeline_status(
        self,
        project_id: str | None = None,
    ) -> dict:
        """파트너 신청 파이프라인 단계별 현황 요약."""
        pid = project_id or PARTNER_SOURCE_PROJECT
        all_tasks = self.list_all_tasks(pid)

        # 마일스톤별 그룹핑
        stages: dict[str, list] = {}
        no_stage = []
        for t in all_tasks:
            ms = t.get("milestone")
            stage_name = ms.get("name", "") if ms and isinstance(ms, dict) else ""
            if stage_name:
                stages.setdefault(stage_name, []).append(t)
            else:
                no_stage.append(t)

        # 정렬: 파트너 신청 단계 순서
        stage_order = ["1. 인입", "2. 정책안내", "3. 법무검토", "4. 계약서 - Slam", "5. 사업기안", "6. 날인", "7. 완료", "8. 드랍"]
        pipeline = []
        for stage in stage_order:
            tasks_in_stage = stages.pop(stage, [])
            # working 상태만 카운트
            active = [t for t in tasks_in_stage if t.get("workflowClass") in ("registered", "working")]
            pipeline.append({
                "단계": stage,
                "전체": len(tasks_in_stage),
                "진행중": len(active),
                "태스크": [
                    {"id": t["id"], "제목": t.get("subject", ""), "상태": t.get("workflowClass", "")}
                    for t in active
                ],
            })

        # 나머지 (정의되지 않은 단계)
        for stage_name, tasks_in_stage in stages.items():
            active = [t for t in tasks_in_stage if t.get("workflowClass") in ("registered", "working")]
            pipeline.append({
                "단계": stage_name,
                "전체": len(tasks_in_stage),
                "진행중": len(active),
                "태스크": [
                    {"id": t["id"], "제목": t.get("subject", ""), "상태": t.get("workflowClass", "")}
                    for t in active
                ],
            })

        return {
            "파이프라인": pipeline,
            "총_건수": len(all_tasks),
            "미분류": len(no_stage),
        }

    # ── Phase 6: 보고/현황/누락방지 ────────────────────────

    def project_summary(self, project_id: str | None = None) -> dict:
        """프로젝트 전체 현황 집계.

        상태별/마일스톤별/담당자별/태그별 건수 + 최근 변경.
        """
        all_tasks = self.list_all_tasks(project_id)

        by_workflow = {}
        by_milestone = {}
        by_assignee = {}
        by_tag = {}

        for t in all_tasks:
            # 상태별
            wf = t.get("workflowClass", "unknown")
            by_workflow[wf] = by_workflow.get(wf, 0) + 1

            # 마일스톤별
            ms = t.get("milestone")
            ms_name = ms.get("name", "없음") if ms and isinstance(ms, dict) else "없음"
            by_milestone[ms_name] = by_milestone.get(ms_name, 0) + 1

            # 담당자별
            assignees = t.get("users", {}).get("to", [])
            if assignees:
                for u in assignees:
                    name = u.get("member", {}).get("name", "미지정")
                    by_assignee[name] = by_assignee.get(name, 0) + 1
            else:
                by_assignee["미지정"] = by_assignee.get("미지정", 0) + 1

            # 태그별
            for tag in t.get("tags", []):
                tag_name = tag.get("name", "")
                if tag_name:
                    by_tag[tag_name] = by_tag.get(tag_name, 0) + 1

        return {
            "총_건수": len(all_tasks),
            "상태별": dict(sorted(by_workflow.items(), key=lambda x: -x[1])),
            "마일스톤별": dict(sorted(by_milestone.items(), key=lambda x: -x[1])),
            "담당자별": dict(sorted(by_assignee.items(), key=lambda x: -x[1])),
            "태그별": dict(sorted(by_tag.items(), key=lambda x: -x[1])),
        }

    def find_stale_tasks(
        self,
        project_id: str | None = None,
        days: int = 7,
    ) -> list[dict]:
        """지정 기간 이상 변경 없는 진행중 태스크 찾기 (누락 방지).

        Args:
            days: 경과 일수 기준 (기본 7일)
        """
        import re as _re
        from datetime import datetime, timedelta, timezone

        KST = timezone(timedelta(hours=9))
        cutoff = datetime.now(KST) - timedelta(days=days)
        all_tasks = self.list_all_tasks(project_id)

        stale = []
        for t in all_tasks:
            # 진행중 상태(closed 제외)만 대상
            wf_class = t.get("workflowClass", "")
            if wf_class in ("closed", "archived"):
                continue

            updated = t.get("updatedAt", "") or t.get("createdAt", "")
            if not updated:
                stale.append(t)
                continue

            # ISO → datetime 비교
            try:
                # "2026-03-20T10:00:00+09:00" 형식
                dt_str = str(updated).replace("+09:00", "+0900").replace("+00:00", "+0000")
                # 간단 파싱: 날짜 부분만
                date_part = str(updated).split("T")[0]
                task_date = datetime.strptime(date_part, "%Y-%m-%d").replace(tzinfo=KST)
                if task_date < cutoff:
                    stale.append(t)
            except (ValueError, IndexError):
                pass

        return stale

    def audit_task_quality(self, project_id: str | None = None) -> dict:
        """태스크 품질 점검 - 누락 항목 찾기.

        체크 항목:
        - 담당자 미지정
        - 본문 비어있음
        - 태그 없음
        - 마일스톤 없음
        """
        all_tasks = self.list_all_tasks(project_id)
        issues = {
            "담당자_미지정": [],
            "본문_비어있음": [],
            "태그_없음": [],
            "마일스톤_없음": [],
        }

        for t in all_tasks:
            wf_class = t.get("workflowClass", "")
            if wf_class in ("closed", "archived"):
                continue

            tid = t.get("id", "")
            subj = t.get("subject", "")
            entry = {"id": tid, "제목": subj}

            # 담당자 체크
            assignees = t.get("users", {}).get("to", [])
            if not assignees:
                issues["담당자_미지정"].append(entry)

            # 본문 체크
            body = t.get("body", {})
            content = body.get("content", "") if isinstance(body, dict) else ""
            if not content or len(content.strip()) < 10:
                issues["본문_비어있음"].append(entry)

            # 태그 체크
            if not t.get("tags"):
                issues["태그_없음"].append(entry)

            # 마일스톤 체크
            ms = t.get("milestone")
            if not ms or not (isinstance(ms, dict) and ms.get("name")):
                issues["마일스톤_없음"].append(entry)

        return {
            "총_점검": len([t for t in all_tasks if t.get("workflowClass") not in ("closed", "archived")]),
            "이슈": {k: {"건수": len(v), "목록": v} for k, v in issues.items()},
        }

    def find_duplicates(self, project_id: str | None = None) -> list[dict]:
        """제목 기반 중복 태스크 탐지."""
        import re as _re

        all_tasks = self.list_all_tasks(project_id)

        # 제목 정규화: 날짜 접두사, 공백, 특수문자 제거
        def normalize(s):
            s = _re.sub(r"^\d{4}[/.-]\d{2}[/.-]\d{2}\s*[-–]\s*", "", s)
            s = _re.sub(r"\[.*?\]", "", s)
            s = s.strip().lower()
            s = _re.sub(r"\s+", " ", s)
            return s

        by_name: dict[str, list] = {}
        for t in all_tasks:
            key = normalize(t.get("subject", ""))
            if key:
                by_name.setdefault(key, []).append(t)

        duplicates = []
        for key, tasks in by_name.items():
            if len(tasks) > 1:
                duplicates.append({
                    "정규화_제목": key,
                    "건수": len(tasks),
                    "태스크": [
                        {
                            "id": t["id"],
                            "제목": t.get("subject", ""),
                            "상태": t.get("workflowClass", ""),
                        }
                        for t in tasks
                    ],
                })

        return sorted(duplicates, key=lambda x: -x["건수"])

    def parse_task_body(self, post_id: str, project_id: str | None = None) -> dict:
        """태스크 본문에서 구조화된 데이터 추출.

        마크다운 테이블, key: value 패턴, 체크박스 등을 파싱.
        """
        import re as _re

        task = self.get_task(post_id, project_id)
        body = task.get("body", {})
        content = body.get("content", "") if isinstance(body, dict) else ""

        if not content.strip():
            return {"post_id": post_id, "parsed": {}, "message": "본문이 비어있습니다."}

        parsed = {}

        # 1. 마크다운 테이블 파싱: | key | value |
        table_rows = _re.findall(r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|", content)
        for key, val in table_rows:
            key = key.strip().rstrip("*").strip()
            val = val.strip().rstrip("*").strip()
            if key and val and key != "---" and not key.startswith("-"):
                parsed[key] = val

        # 2. "key: value" 또는 "- key: value" 패턴
        kv_lines = _re.findall(r"[-*]?\s*\*?\*?(.+?)\*?\*?\s*[:：]\s*(.+)", content)
        for key, val in kv_lines:
            key = key.strip().rstrip("*").strip()
            val = val.strip()
            if key and val and len(key) < 30:
                parsed[key] = val

        # 3. 체크박스: - [x] item / - [ ] item
        checkboxes = {}
        for match in _re.finditer(r"-\s*\[([ xX])\]\s*(.+)", content):
            checked = match.group(1).lower() == "x"
            item = match.group(2).strip()
            checkboxes[item] = checked
        if checkboxes:
            parsed["체크박스"] = checkboxes

        # 4. 이메일 추출
        emails = _re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", content)
        if emails:
            parsed["이메일"] = list(set(emails))

        # 5. 사업자등록번호 추출
        bizno = _re.findall(r"\d{3}-\d{2}-\d{5}", content)
        if bizno:
            parsed["사업자등록번호"] = list(set(bizno))

        # 6. URL 추출
        urls = _re.findall(r"https?://[^\s\)]+", content)
        if urls:
            parsed["URL"] = list(set(urls))

        return {
            "post_id": post_id,
            "제목": task.get("subject", ""),
            "parsed": parsed,
            "필드수": len(parsed),
        }

    def get_weekly_changes(
        self,
        project_id: str | None = None,
        days: int = 7,
    ) -> dict:
        """최근 N일간 변경된 태스크 요약 (주간보고용).

        생성/수정/완료 분류하여 요약.
        """
        from datetime import datetime, timedelta, timezone

        KST = timezone(timedelta(hours=9))
        cutoff = datetime.now(KST) - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        all_tasks = self.list_all_tasks(project_id)

        created = []
        updated = []
        closed = []

        for t in all_tasks:
            created_at = str(t.get("createdAt", "")).split("T")[0]
            updated_at = str(t.get("updatedAt", "")).split("T")[0]
            wf_class = t.get("workflowClass", "")

            entry = {
                "id": t["id"],
                "제목": t.get("subject", ""),
                "상태": wf_class,
                "담당자": [
                    u.get("member", {}).get("name", "")
                    for u in t.get("users", {}).get("to", [])
                ],
                "생성일": created_at,
                "수정일": updated_at,
            }

            if created_at >= cutoff_str:
                created.append(entry)

            if wf_class in ("closed", "archived") and updated_at >= cutoff_str:
                closed.append(entry)
            elif updated_at >= cutoff_str and created_at < cutoff_str:
                updated.append(entry)

        return {
            "기간": f"{cutoff_str} ~ {datetime.now(KST).strftime('%Y-%m-%d')}",
            "신규": {"건수": len(created), "목록": created},
            "수정": {"건수": len(updated), "목록": updated},
            "완료": {"건수": len(closed), "목록": closed},
            "요약": f"신규 {len(created)}건, 수정 {len(updated)}건, 완료 {len(closed)}건",
        }

    def search_across_projects(
        self,
        keyword: str,
        project_ids: list[str] | None = None,
    ) -> dict:
        """여러 프로젝트에서 동시 검색.

        Args:
            keyword: 검색어 (필수)
            project_ids: 검색할 프로젝트 ID/별칭 리스트 (미지정 시 등록된 전체)
        """
        from .projects import load_projects

        if not keyword or not keyword.strip():
            raise ValidationError("검색어가 비어있습니다.")

        keyword = keyword.strip().lower()

        # 대상 프로젝트 결정
        if project_ids:
            targets = [(pid, pid) for pid in project_ids]
        else:
            projects = load_projects()
            targets = [(alias, info["id"]) for alias, info in list(projects.items())[:20]]

        if not targets:
            raise ValidationError("검색할 프로젝트가 없습니다. dooray_discover_projects를 먼저 실행하세요.")

        results = []
        for label, pid in targets:
            try:
                resolved = self._resolve_project(pid)
                tasks = self.list_all_tasks(resolved)
                matched = [
                    t for t in tasks
                    if keyword in t.get("subject", "").lower()
                ]
                if matched:
                    results.append({
                        "프로젝트": label,
                        "project_id": resolved,
                        "매칭": len(matched),
                        "태스크": [
                            {"id": t["id"], "제목": t.get("subject", "")}
                            for t in matched[:10]
                        ],
                    })
            except Exception:
                continue

        total = sum(r["매칭"] for r in results)
        return {
            "검색어": keyword,
            "검색_프로젝트수": len(targets),
            "매칭_프로젝트수": len(results),
            "총_매칭": total,
            "결과": results,
        }
