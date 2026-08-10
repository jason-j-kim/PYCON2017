# KWCI L3 통합 토픽·키워드 사전 — 잠정판

**생성 2026-08-10 01:35 UTC · 1,523행 · 18개국 · 11개 언어**

> **이 파일을 그대로 분석에 쓰지 마십시오.** 1,073행이 Trends 실측을
> 거치지 않았습니다. 신호 유무·표기 타당성·MID 존재가 전부 미확인입니다.
> 실측으로 무신호 행을 걸러낸 뒤라야 계열이 됩니다.

## 구성

| 도메인 | 행 | 출처 | 검증 |
|---|---|---|---|
| KPOP | 396 | 기존 486행 사전 | 실증 통과 |
| KFOOD | 322 | 신규 (조합 생성) | **미실증** |
| KFASHION | 287 | 신규 (조합 생성) | **미실증** |
| KBEAUTY | 286 | 신규 (조합 생성) | **미실증** |
| KTOURISM | 178 | 신규 (의도어 문법) | **미실증** |
| KVIDEO | 54 | 기존 486행 사전 | 실증 통과 |
| **합계** | **1,523** | | 실증 450 / 대기 1073 |

## 출처 파일

| 파일 | sha256 |
|---|---|
| `ef23b4c0-KWCI_final_topic_keyword_dictionary_486_with_technical_status.csv` | `42f0537e20229d34…` |
| `tourism/ktourism_dict.csv` | `5e540556dfdc6f84…` |
| `consumer/kconsumer_dict.csv` | `bbb45b7ec797bee5…` |

## 조립 내역

- 기존 사전에서 승계: 450행
- 관광 신규: 178행 (기존 36행 대체)
- 소비재 신규: 895행

## 상태 판독법

행마다 다음 열로 검증 수준을 읽습니다.

| 열 | 값 | 뜻 |
|---|---|---|
| `empirical_validation_status` | `EMPIRICALLY_VALIDATED` | Trends 실측 통과 |
| | `NOT_YET_TESTED` | **미실측** |
| `technical_status` | `PENDING_TOPIC_EXTRACTION` | MID 추출 대상 |
| | `PENDING_DOM_EXTRACTION` | 신호 유무만 확인 |
| `selection_basis` | `EXPORT_REFERENCED` | 수출 품목이 범주를 지정 |
| | `MODE_GRAMMAR` / `RULE_GRAMMAR` | 소비양식 문법 (설계 재량 있음) |
| `extraction_method` | `COMPOSED` | 원산지×명사 조합 생성 |
| | `ATOMIC_LEXEME` | 외래어 개별 표기 |
| `ambiguity_flag` | `JP_DOMESTIC_COUNTERPART` | 일본 자국 대응물 오염 |
| `remaining_risk` | (자유 서술) | 그 개념이 못 잡는 것 |

## 재생성

```
python build_master_dict.py --base <486행 사전.csv>
```

도메인 사전을 먼저 다시 만든 뒤 합칩니다. 결정론적이라 같은 입력이면
같은 해시가 나옵니다.

자세한 설계 근거는 `docs/00_인수인계.md` 와 `docs/01~03` 을 보십시오.
