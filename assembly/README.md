# 국회 토론회 레이더 — 자동화

매일 열린국회정보 Open API에서 세미나/토론회 일정을 받아
`docs/seminars.json`으로 저장하고, `docs/index.html`이 이를 읽어 표시한다.

```
GitHub Actions (매일 08:00 KST)
  └ assembly/fetch_seminars.py   API 호출 + 정규화
      └ docs/seminars.json       커밋
          └ docs/index.html      __DATA_URL__로 읽어 표시 (GitHub Pages)
```

## 설정 (1회)

### 1. API 키를 Secret에 등록
공공데이터/열린국회 인증키를 코드가 아닌 Secret에 둔다.

`Settings → Secrets and variables → Actions → New repository secret`
- Name: `ASSEMBLY_API_KEY`
- Value: 발급받은 인증키

> 키를 코드·커밋에 절대 넣지 말 것. 노출되면 발급기관에서 폐기·재발급.

### 2. Actions 권한 확인
`Settings → Actions → General → Workflow permissions`에서
**Read and write permissions**를 켠다. (봇이 `seminars.json`을 커밋해야 함)

### 3. GitHub Pages 켜기 (화면 공개용, 선택)
`Settings → Pages → Source: Deploy from a branch`
- Branch: 데이터가 있는 브랜치 / 폴더 `/docs`

공개 주소: `https://<계정>.github.io/<repo>/`

### 4. 첫 실행
`Actions → 국회 토론회 일일 수집 → Run workflow`로 수동 실행해
`docs/seminars.json`이 생성되는지 확인한다. 이후 매일 자동 실행된다.

## 로컬 테스트

```bash
pip install requests
ASSEMBLY_API_KEY=발급키 python assembly/fetch_seminars.py
# → docs/seminars.json 생성
```

## 동작 메모

- 서비스 ID는 env로 교체 가능:
  `ASSEMBLY_SERVICE_SEMINAR`(일정), `ASSEMBLY_SERVICE_HOSTING`(개최현황: 발제자·토론자).
- API 에러 봉투(`RESULT.CODE`)를 검사한다. `INFO-200`(데이터 없음)은 정상 종료,
  키/권한 오류는 실패 처리하여 기존 JSON을 덮어쓰지 않는다.
- 키워드 필터·중요도 점수·기간 필터는 화면(`index.html`)에서 처리한다.
  수집기는 정규화된 원본만 내보낸다.
- `seminars.json`이 아직 없으면 화면은 내장 샘플로 표시된다(첫 실행 전 정상 동작).
