# 프롬프트 프로토타입 (전략 1단계)

`docs/socratic-idea-evaluation-strategy.md` 로드맵의 1단계 — 웹을 만들기 전에
질문자·채점자 프롬프트의 품질을 CLI로 먼저 검증한다.

## 구성

핵심 로직(프롬프트, 상태 머신 단계 정의, 질문자/채점자 호출)은 웹 MVP와 공유하는
`socratic/` 패키지에 있다. 이 디렉터리는 그 터미널 프런트엔드다.

```
socratic/
├── engine.py                  # 공유 엔진: 단계 정의, claude 호출, 채점 파싱
└── prompts/
    ├── questioner_system.md   # 질문자: 산파술 규칙, 6가지 질문 유형, 어조 규칙
    └── grader_system.md       # 채점자: 루브릭, 턴 인용 강제, 격려 규칙
prototype/
├── socratic_cli.py            # 전체 세션 실행 (문답 → 채점 → 리포트 → JSON 저장)
└── README.md
```

전략의 핵심 설계가 그대로 구현되어 있다:

- **질문자와 채점자 분리** — 별도 API 호출. 질문자는 점수를 모르고, 채점자는
  대화에 참여하지 않고 로그만 본다.
- **서버 측 상태 머신** — 단계 전이(명료화 → 독창성 → 실용성 → 수용태도 →
  자기 평가)는 파이썬 코드가 강제하고, LLM에는 매 턴 현재 단계 지시만 주입한다.
- **설명 가능한 채점** — 채점 결과는 JSON으로 받아 파싱·검증하고(실패 시 자동
  재시도), 모든 하위 점수에 대화 턴 번호 인용을 요구한다. 가중 평균은 코드가
  계산한다.

## 실행

**API 키가 필요 없다.** 백엔드로 Claude Code CLI(`claude -p`)를 사용하므로,
Claude Pro/Max 구독 계정으로 로그인만 되어 있으면 된다. 파이썬 패키지 설치도 없다
(표준 라이브러리만 사용).

```bash
# 최초 1회: Claude Code 설치(https://claude.com/claude-code) 후 로그인
claude /login

# 저장소 루트에서
python prototype/socratic_cli.py

# 가중치 조정 (합이 1이어야 함)
python prototype/socratic_cli.py --w-orig 0.5 --w-prac 0.3 --w-acc 0.2
```

- 문답 중 `q` 를 입력하면 남은 라운드를 건너뛰고 바로 채점한다.
- 세션 종료 시 대화 로그·점수·근거가 `session_*.json` 으로 저장된다.

## 이 단계에서 실험할 것

1. **문답의 질** — 질문이 실제로 스스로 깨닫게 만드는가, 심문처럼 느껴지지
   않는가. `socratic/prompts/questioner_system.md` 의 어조 규칙과 질문 유형을 다듬는다.
2. **채점 일관성** — 같은 `session_*.json` 의 transcript를 채점자에 여러 번
   넣어 점수 분산을 확인한다. 분산이 크면 루브릭의 하위 지표 정의를 더 잘게 쪼갠다.
3. **회피/장난 답변 내성** — 일부러 모호하게 답해 보고 재질문·감점 규칙이
   작동하는지 확인한다.

2단계 웹 MVP는 `webapp/` 에 구현되어 있으며, 같은 `socratic/engine.py` 를
사용하므로 여기서 프롬프트를 다듬으면 웹에도 그대로 반영된다.
