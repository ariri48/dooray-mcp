# Dooray MCP Server

Dooray 태스크 관리를 위한 [Model Context Protocol](https://modelcontextprotocol.io/) 서버입니다.
Claude Code에서 Dooray 태스크를 조회, 생성, 수정할 수 있습니다.

## 설치 (3단계)

### 1. 레포 복제

```bash
git clone https://github.com/ariri48/dooray-mcp.git
cd dooray-mcp
```

### 2. 설치 마법사 실행

```bash
python setup.py
```

마법사가 아래를 자동 처리합니다:
- Dooray API 토큰 입력 및 `.env` 생성
- Python 의존성 설치
- API 연결 검증
- 프로젝트 자동 탐색
- Claude Code MCP 서버 등록

### 3. Claude Code 재시작

Claude Code를 새로 시작하면 바로 사용할 수 있습니다.

## 사전 준비

- **Python 3.10 이상**
- **Claude Code** 설치 완료
- **Dooray API 토큰**: Dooray > 설정 > API 토큰에서 발급

## 주요 기능

| 기능 | 설명 |
|------|------|
| 태스크 조회 | 프로젝트별 태스크 목록, 상세 조회 |
| 태스크 생성 | 새 태스크, 하위 태스크 생성 |
| 태스크 수정 | 상태, 담당자, 태그, 마일스톤 변경 |
| 댓글 | 태스크 댓글 조회 및 작성 |
| 검색 | 키워드 기반 태스크 검색 |
| 내 태스크 | 나에게 할당된 태스크 조회 |
| 프로젝트 탐색 | 접근 가능한 프로젝트 자동 탐색 |

## 사용 예시

Claude Code에서 자연어로 요청하세요:

```
"내 태스크 보여줘"
"파트너신청 프로젝트에 새 태스크 만들어줘"
"태스크 12345678 상태를 완료로 변경해줘"
```

## 수동 설치 (setup.py 없이)

```bash
pip install mcp[cli] requests python-dotenv
cp .env.example .env
# .env 파일에 API 토큰 입력
claude mcp add dooray-mcp -s user -- python /path/to/dooray-mcp/run_server.py
```

## 라이선스

MIT
