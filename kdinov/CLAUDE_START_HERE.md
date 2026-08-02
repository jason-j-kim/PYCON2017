# Claude용 KDI 코퍼스 판정기 최소 인계 패키지

## 목표

정책 아이디어를 `대상 × 수단 × 영역`으로 구조화하고 KDI SQLite 코퍼스와 대조하여,
문헌별 중첩도(`N0~N4`)와 활용 역할(`실행/경합/근거/선례/무관`)을 근거 문장과 함께 판정한다.

## 반드시 읽을 순서

1. `README.md` — 전체 작동 원리, 설치·실행법, 판정표
2. `HANDOFF.md` — 설계 근거, 실제 오판정 이력, 한계
3. `reports/kdi_policy_originality_judger_design.md` — 비개발자용 판정 원칙 설명
4. `kdinov/model.py`, `score.py`, `verdict.py` — 실제 판정 구현
5. `tests/test_pipeline.py` — 규칙이 지켜야 할 회귀 사례

## 핵심 원칙

- 검색 0건을 곧바로 신규라고 판정하지 않는다.
- 중첩 정도와 문헌 활용 방식을 분리한다.
- `known_positives`가 회수되지 않으면 결론은 `VOID`다.
- 같은 키워드가 한 문헌에 존재하는 것과 같은 문장·목차 단위에서 공기하는 것을 구분한다.
- 정책의 방향이 반대인 문헌을 직접 중첩으로 오인하지 않는다.
- 법령·시행령·보도자료 등 이미 집행된 정책은 단순 연구문헌보다 강한 반증이다.
- 결과는 최종 확정이 아니라 사람이 검토할 후보 목록이며 근거 문장을 항상 남긴다.

## SQLite 연결

대용량 원본 DB는 이 ZIP에 포함하지 않았다. 기존 파일 `D:\work\kdinov\kdi.sqlite`를
프로젝트 루트에 두거나 실행 시 절대경로로 지정한다.

```powershell
python -m kdinov judge --db "D:\work\kdinov\kdi.sqlite" --idea ideas\sme_ai_edu.json -o report.md
```

## 독립 검증

ZIP에 포함된 소형 코퍼스와 테스트만으로 판정 로직을 검증할 수 있다.

```powershell
pip install -e ".[dev]"
python -m pytest tests -q
```

## Claude에게 줄 작업 지시의 핵심

기존 판정 의미와 회귀 테스트를 먼저 보존하라. 규칙을 수정할 때는 실제 오판정 사례를
추가 테스트로 고정하라. `N4`나 검색 0건을 신규성 확정으로 표현하지 말고, 코퍼스 범위와
재현율 통제 결과를 함께 보고하라. 비밀키를 코드나 결과물에 넣지 말라.
