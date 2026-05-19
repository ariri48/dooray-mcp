"""validators.py 단위 테스트 — 데이터 신뢰성의 근간"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.validators import (
    ValidationError,
    validate_api_response,
    validate_task,
    validate_task_list,
    validate_project_id,
    validate_post_id,
    validate_subject,
    validate_body_content,
    validate_tag_names,
    validate_pagination,
    clean_task_for_display,
    danger_summary,
)


# ── API 응답 검증 테스트 ──────────────────────────────────


class TestValidateApiResponse:
    def test_성공_응답(self):
        resp = {"header": {"isSuccessful": True}, "result": [{"id": "1"}]}
        assert validate_api_response(resp, "test") == [{"id": "1"}]

    def test_실패_응답(self):
        resp = {
            "header": {
                "isSuccessful": False,
                "resultCode": "NOT_FOUND",
                "resultMessage": "리소스 없음",
            }
        }
        with pytest.raises(ValidationError, match="NOT_FOUND"):
            validate_api_response(resp, "test")

    def test_잘못된_형식(self):
        with pytest.raises(ValidationError, match="올바른 JSON"):
            validate_api_response("not a dict", "test")

    def test_헤더_누락(self):
        with pytest.raises(ValidationError):
            validate_api_response({}, "test")


# ── 태스크 검증 테스트 ────────────────────────────────────


class TestValidateTask:
    def test_정상_태스크(self):
        task = {"id": "123", "subject": "테스트"}
        assert validate_task(task) == task

    def test_필수필드_누락(self):
        with pytest.raises(ValidationError, match="필수 필드"):
            validate_task({"id": "123"})

    def test_비어있는_subject(self):
        with pytest.raises(ValidationError, match="필수 필드"):
            validate_task({"id": "123", "subject": ""})

    def test_본문_필수시_누락(self):
        with pytest.raises(ValidationError, match="본문"):
            validate_task({"id": "1", "subject": "test"}, require_body=True)

    def test_딕셔너리_아닌_경우(self):
        with pytest.raises(ValidationError, match="올바른 형식"):
            validate_task("not a dict")


class TestValidateTaskList:
    def test_정상_목록(self):
        tasks = [
            {"id": "1", "subject": "A"},
            {"id": "2", "subject": "B"},
        ]
        result = validate_task_list(tasks)
        assert len(result) == 2

    def test_불량_항목_건너뜀(self):
        tasks = [
            {"id": "1", "subject": "A"},
            {"id": "2"},  # subject 누락
            {"id": "3", "subject": "C"},
        ]
        result = validate_task_list(tasks)
        assert len(result) == 2


# ── 입력값 검증 테스트 ────────────────────────────────────


class TestValidateProjectId:
    def test_정상_ID(self):
        assert validate_project_id("4118231653304784792") == "4118231653304784792"

    def test_기본값_사용(self):
        assert validate_project_id(None, "12345") == "12345"

    def test_둘다_없음(self):
        with pytest.raises(ValidationError, match="project_id"):
            validate_project_id(None, None)

    def test_숫자가_아닌_경우(self):
        with pytest.raises(ValidationError, match="숫자만"):
            validate_project_id("abc-def")


class TestValidatePostId:
    def test_정상(self):
        assert validate_post_id("123456") == "123456"

    def test_비어있음(self):
        with pytest.raises(ValidationError, match="비어있"):
            validate_post_id("")

    def test_잘못된_형식(self):
        with pytest.raises(ValidationError, match="숫자만"):
            validate_post_id("abc")


class TestValidateSubject:
    def test_정상(self):
        assert validate_subject("테스트 태스크") == "테스트 태스크"

    def test_공백만(self):
        with pytest.raises(ValidationError, match="비어있"):
            validate_subject("   ")

    def test_너무_긴_제목(self):
        with pytest.raises(ValidationError, match="너무 깁니다"):
            validate_subject("x" * 501)


class TestValidateTagNames:
    def test_정상(self):
        assert validate_tag_names(["리셀링", "Notification"]) == ["리셀링", "Notification"]

    def test_빈_리스트(self):
        assert validate_tag_names([]) == []

    def test_None(self):
        assert validate_tag_names(None) == []

    def test_공백_이름(self):
        with pytest.raises(ValidationError, match="올바르지 않은"):
            validate_tag_names(["  "])


class TestValidatePagination:
    def test_정상(self):
        assert validate_pagination(0, 50) == (0, 50)

    def test_음수_페이지(self):
        with pytest.raises(ValidationError, match="0 이상"):
            validate_pagination(-1, 50)

    def test_범위_초과(self):
        with pytest.raises(ValidationError, match="1~100"):
            validate_pagination(0, 200)


# ── 데이터 정제 테스트 ────────────────────────────────────


class TestCleanTaskForDisplay:
    def test_기본_정제(self):
        task = {
            "id": "123",
            "subject": "테스트 태스크",
            "workflowClass": "registered",
            "milestone": {"name": "인입"},
            "users": {"to": [{"member": {"name": "홍길동"}}]},
            "tags": [{"name": "리셀링"}, {"name": "Dooray"}],
            "createdAt": "2026-03-25T10:00:00+09:00",
            "updatedAt": "2026-03-26T14:30:00+09:00",
        }
        cleaned = clean_task_for_display(task)
        assert cleaned["id"] == "123"
        assert cleaned["제목"] == "테스트 태스크"
        assert cleaned["담당자"] == ["홍길동"]
        assert cleaned["태그"] == ["리셀링", "Dooray"]
        assert cleaned["단계"] == "인입"
        assert cleaned["생성일"] == "2026-03-25"

    def test_빈_담당자(self):
        task = {"id": "1", "subject": "test", "users": {}}
        cleaned = clean_task_for_display(task)
        assert cleaned["담당자"] == ["미지정"]


# ── 위험 작업 요약 테스트 ─────────────────────────────────


class TestDangerSummary:
    def test_기본_메시지(self):
        msg = danger_summary("태스크 삭제", "테스트(123)")
        assert "태스크 삭제" in msg
        assert "테스트(123)" in msg
        assert "되돌릴 수 없" in msg

    def test_상세정보_포함(self):
        msg = danger_summary("삭제", "태스크", {"상태": "진행중", "태그": "리셀링"})
        assert "진행중" in msg
        assert "리셀링" in msg
