# 프롬프트 프로토타입 (전략 1단계)

`docs/socratic-idea-evaluation-strategy.md` 로드맵의 1단계 — 웹을 만들기 전에
질문자·채점자 프롬프트의 품질을 CLI로 먼저 검증한다.

## 구성

```
prototype/
├── prompts/
│   ├── questioner_system.md   # 질문자: 산파술 규칙, 6가지 질문 유형, 어조 규칙
│   └── grader_system.md       # 채점자: 루브릭, 턴 인용 강제, 격려 규칙
├── socratic_cli.py            # 전체 세션 실행 (문답 → 채점 → 리포트 → JSON 저장)
└── README.md
```

전략의 핵심 설계가 그대로 구현되어 있다:

- **질문자와 채점자 분리** — 별도 API 호출. 질문자는 점수를 모르고, 채점자는
  대화에 참여하지 않고 로그만 본다.
- **서버 측 상태 머신** — 단계 전이(명료화 → 독창성 → 실용성 → 수용태도 →
  자기 평가)는 파이썬 코드가 강제하고, LLM에는 매 턴 현재 단계 지시만 주입한다.
- **설명 가능한 채점** — 채점은 JSON 스키마 강제(structured output)로 받고,
  모든 하위 점수에 대화 턴 번호 인용을 요구한다. 가중 평균은 코드가 계산한다.

## 실행

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-...
python socratic_cli.py

# 가중치 조정 (합이 1이어야 함)
python socratic_cli.py --w-orig 0.5 --w-prac 0.3 --w-acc 0.2
```

- 문답 중 `q` 를 입력하면 남은 라운드를 건너뛰고 바로 채점한다.
- 세션 종료 시 대화 로그·점수·근거가 `session_*.json` 으로 저장된다.

## 이 단계에서 실험할 것

1. **문답의 질** — 질문이 실제로 스스로 깨닫게 만드는가, 심문처럼 느껴지지
   않는가. `prompts/questioner_system.md` 의 어조 규칙과 질문 유형을 다듬는다.
2. **채점 일관성** — 같은 `session_*.json` 의 transcript를 채점자에 여러 번
   넣어 점수 분산을 확인한다. 분산이 크면 루브릭의 하위 지표 정의를 더 잘게 쪼갠다.
3. **회피/장난 답변 내성** — 일부러 모호하게 답해 보고 재질문·감점 규칙이
   작동하는지 확인한다.

여기서 프롬프트가 안정되면 2단계(FastAPI + 웹 채팅 UI)로 넘어간다. CLI의
`ask_questioner` / `grade` 함수가 그대로 웹 백엔드의 대화 엔진·채점 엔진이 된다.
