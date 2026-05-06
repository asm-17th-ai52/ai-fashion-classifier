# AI 패션 상황 추천 Agent — Spec 문서

본 디렉토리는 52조 프로젝트의 AI native 개발을 위한 사양 문서 집합입니다.

## 핵심 원칙

1. **정량화 우선**: 모든 Agent 출력은 숫자 점수 + 명시적 rubric
2. **결정성**: 점수 계산은 순수 함수, LLM은 자연어화 역할만
3. **주관적 평가 금지**: 매력/호감/인상/성격 등 사회심리 추론은 시스템 범위 외
4. **Schema-First**: 모든 인터페이스는 schema 머지 후 구현

## 읽는 순서

| 순서 | 문서 | 대상 |
|---|---|---|
| 1 | [00-overview.md](./00-overview.md) | 전원 (필독) |
| 2 | [01-architecture.md](./01-architecture.md) | 전원 |
| 3 | [07-data-contracts.md](./07-data-contracts.md) | 전원 (필독) |
| 4 | [08-roles-and-handoffs.md](./08-roles-and-handoffs.md) | 전원 (필독) |
| 5 | [02-agent-vision-spec.md](./02-agent-vision-spec.md) | Vision 담당 |
| 6 | [03-agent-context-spec.md](./03-agent-context-spec.md) | Context 담당 |
| 7 | [04-agent-recommendation-spec.md](./04-agent-recommendation-spec.md) | Recommendation 담당 |
| 8 | [05-backend-spec.md](./05-backend-spec.md) | Backend 담당 |
| 9 | [06-frontend-spec.md](./06-frontend-spec.md) | Frontend 담당 |

## 팀 구성

- AI Agent 개발: 3명 (Vision / Context / Recommendation)
- Backend: 1명
- Frontend: 1명

## 참고

원본 기획서는 상위 디렉토리의 PDF 파일을 참조.
