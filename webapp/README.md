# 웹 MVP (전략 2단계)

`docs/socratic-idea-evaluation-strategy.md` 로드맵의 2단계 — 소크라테스 문답
아이디어 평가를 브라우저 채팅 UI로 제공한다. 핵심 로직은 CLI와 동일한
`socratic/engine.py`를 사용한다.

## 실행

**API 키가 필요 없다.** 서버가 로컬의 Claude Code CLI(`claude -p`)를 호출하므로,
서버를 띄우는 컴퓨터에 Claude Pro/Max 구독 계정으로 로그인만 되어 있으면 된다.

```bash
pip install fastapi "uvicorn[standard]"
claude /login                # 최초 1회 (이미 로그인돼 있으면 생략)

# 저장소 루트에서
python webapp/app.py         # → http://localhost:8000
```

## 구성

```
webapp/
├── app.py             # FastAPI: 세션 API + 정적 파일 서빙
├── db.py              # SQLite 저장소 (sessions / turns / evaluations)
├── static/index.html  # 채팅 UI (바닐라 JS 단일 파일)
└── sessions.db        # 실행 시 자동 생성 (커밋하지 않음)
```

## API

| 메서드 | 경로 | 동작 |
|---|---|---|
| `POST` | `/api/sessions` | 세션 생성 + 첫 질문. body: `{idea, weights?}` |
| `POST` | `/api/sessions/{id}/answer` | 답변 제출 → 다음 질문 또는 (마지막이면) 채점 결과 |
| `POST` | `/api/sessions/{id}/finish` | 남은 문답을 건너뛰고 즉시 채점 |
| `GET`  | `/api/sessions/{id}` | 세션 전체 조회 (로그 + 평가 결과) |

상태 머신(명료화 2 → 독창성 3 → 실용성 3 → 수용태도 3 → 자기 평가 1)은 서버가
강제하고, 진행 상태는 DB에 저장되므로 서버를 재시작해도 세션이 유지된다.

## MVP의 알려진 한계 (3단계에서 개선)

- 질문 생성이 스트리밍이 아니라 완성 후 한 번에 표시된다 (CLI 백엔드 특성).
- 로그인/사용자 구분이 없다 — 같은 서버를 쓰는 모두가 세션을 만들 수 있다.
- 브라우저 새로고침 시 진행 중 세션 복원 UI가 없다 (API로는 조회 가능).
- 다중 아이디어 비교, 관리자 뷰, 채점 일관성 검증은 미구현.
