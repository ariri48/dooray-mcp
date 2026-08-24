# .githooks

시크릿이 커밋되는 것을 막는 pre-commit 훅. 저장소에 함께 보관하므로 **클론한 PC마다 한 번만** 연결하면 된다.

```bash
git config core.hooksPath .githooks
```

연결됐는지 확인: `git config core.hooksPath` → `.githooks`

## 무엇을 막나

- **파일명**: `.env`, `accounts.json`, `smtp_accounts.json`, `dooray_token.json`,
  `dooray_config.json`, `*.db`, `*.pem`, `*.key`, 브라우저 프로필 디렉터리
- **내용**(스테이징된 추가 줄만): Dooray API 토큰, Dooray 웹훅 URL,
  `password`/`secret`/`api_key` 하드코딩, 개인키 블록, AWS 액세스 키

`EXAMPLE`·`${VAR}`·`your_`·`여기에` 등 자리표시자로 보이는 값은 통과시킨다.

## 우회

| 상황 | 방법 |
|---|---|
| 예시 값인데 오탐 | 그 줄에 `allowlist secret` 주석 추가 |
| 의도한 커밋 | `git commit --no-verify` |

## 도입 배경

2026-08-24. `partner.yaml` 에 Dooray API 토큰, `bulk-mailer/accounts.json` 에 메일 계정
비밀번호가 평문 커밋되어 있었고, 교육 슬라이드의 실제 토큰이 public GitHub Pages 로
노출되어 있었다. 재발 방지용.
