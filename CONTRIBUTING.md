# 기여 가이드

## 브랜치 네이밍

브랜치는 다음 형식을 사용한다.

```text
{type}/{role}-{task}
```

### Type

```text
feat      기능 추가
fix       버그 수정
docs      문서 수정
test      테스트 추가/수정
refactor  리팩터링
chore     기타 설정/정리
```

### Role

역할 이름은 풀네임을 사용한다.

```text
vision
context
recommendation
backend
frontend
common
```

### 예시

```text
feat/recommendation-fixtures
feat/vision-extractor
feat/context-tier1-rag
feat/backend-session-api
feat/frontend-upload-ui
fix/recommendation-blocker-cap
docs/common-contributing-guide
```

## 커밋 메시지

커밋 메시지는 다음 형식을 권장한다.

```text
type(scope): summary
```

`summary`는 한글로 작성한다.

예시:

```text
feat(recommendation): 목 데이터 추가
fix(scoring): blocker cap 적용 오류 수정
docs(common): 깃허브 컨벤션 추가
test(recommendation): 점수 계산 테스트 추가
```

## PR 규칙

- 하나의 PR에는 하나의 목적만 담는다.
- 서로 다른 역할의 작업을 한 PR에 섞지 않는다.
- 큰 작업은 여러 PR로 나누어 올린다.
- 공통 스키마 변경은 별도 PR로 분리한다.
- `docs/specs/07-data-contracts.md` 변경은 팀원 전체 리뷰를 받는다.
