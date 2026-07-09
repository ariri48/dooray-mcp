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

[Dooray 서비스 API 문서](https://helpdesk.dooray.com/share/pages/9wWo-xwiR66BO5LGshgVTg/2939987647631384419)의
전체 엔드포인트를 지원합니다. (150개 이상의 MCP 툴)

| 서비스 | 기능 |
|--------|------|
| Project (업무) | 태스크 CRUD, 상태/담당자/태그/마일스톤 변경, 댓글, 첨부파일, 검색, 일괄 처리 |
| Project (관리) | 프로젝트 생성/조회, 워크플로우·태그·마일스톤·템플릿 CRUD, 멤버/멤버그룹, 이메일 주소, 이벤트 훅 |
| Common | 조직 멤버 검색/조회, 내 정보, Incoming Hook, 스트림(알림 피드) |
| Calendar | 캘린더 CRUD, 일정 생성/조회/수정/삭제, 구성원 관리 |
| Drive | 드라이브/파일 목록, 업로드/다운로드, 폴더 생성, 복사/이동, 공유 링크 CRUD |
| Wiki | 위키/페이지 CRUD, 제목·본문·참조자 변경, 페이지 이동, 댓글 CRUD, 첨부파일, 공유 링크 |
| Messenger | 1:1 메시지, 채널 생성/조회, 초대/내보내기, 메시지 전송/수정/삭제, 답장, 스레드 |
| Reservation | 자원(회의실) 카테고리/목록, 예약 가능 자원 조회, 예약 CRUD |
| Contacts | 주소록 조회/검색 |
| 범용 | `dooray_api_call` — 임의의 Dooray API를 직접 호출하는 escape hatch |

삭제 계열 툴은 `confirm=true`를 명시해야 실제로 실행됩니다.

## 사용 예시

Claude Code에서 자연어로 요청하세요:

```
"내 태스크 보여줘"
"파트너신청 프로젝트에 새 태스크 만들어줘"
"태스크 12345678 상태를 완료로 변경해줘"
"이번 주 내 일정 보여줘"
"홍길동에게 메신저로 '회의 10분 뒤 시작' 보내줘"
"위키에 배포 가이드 페이지 만들어줘"
"내일 오후 2시에 회의실 예약해줘"
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
