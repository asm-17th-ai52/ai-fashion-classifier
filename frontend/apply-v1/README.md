# V1 적용 패키지

이 폴더의 파일들을 `ai-fashion-classifier/frontend/` 코드베이스에 그대로 복사하면 V1 디자인이 실제 앱에 적용됩니다.

## 파일 매핑

| 이 폴더의 파일 | 코드베이스 경로 |
|---|---|
| `tailwind.config.js` | `frontend/tailwind.config.js` |
| `styles/index.css` | `frontend/src/styles/index.css` |
| `components/Pill.tsx` | `frontend/src/components/Pill.tsx` *(신규)* |
| `components/SectionHead.tsx` | `frontend/src/components/SectionHead.tsx` *(신규)* |
| `components/TopNav.tsx` | `frontend/src/components/TopNav.tsx` *(신규)* |
| `components/ScoreGauge.tsx` | `frontend/src/components/ScoreGauge.tsx` *(교체)* |
| `components/ChecklistSection.tsx` | `frontend/src/components/ChecklistSection.tsx` *(교체)* |
| `components/SuggestionCard.tsx` | `frontend/src/components/SuggestionCard.tsx` *(교체)* |
| `components/ImageDropzone.tsx` | `frontend/src/components/ImageDropzone.tsx` *(교체)* |
| `components/EventForm.tsx` | `frontend/src/components/EventForm.tsx` *(교체)* |
| `pages/UploadPage.tsx` | `frontend/src/pages/UploadPage.tsx` *(교체)* |
| `pages/AnalyzingPage.tsx` | `frontend/src/pages/AnalyzingPage.tsx` *(교체)* |
| `pages/ResultPage.tsx` | `frontend/src/pages/ResultPage.tsx` *(교체)* |

## 변경사항 요약

- **Tailwind**: V1 토큰 추가 (`panel`, `panelHi`, `hairline2`, `accent-yellow-soft` 등). 기존 토큰은 유지.
- **신규 컴포넌트 3종**: `<Pill>`, `<SectionHead>`, `<TopNav>` — 모든 페이지에서 재사용.
- **ScoreGauge**: linear bar → 60-tick radial dial + glow.
- **ChecklistSection**: list view → 5-band matrix heatmap + detail rows.
- **SuggestionCard**: action pill + ID prefix + before→after diff visual.
- **AnalyzingPage**: 4-step rows → 4 progress bars + terminal log stream.
- **UploadPage**: form-only → 2-column with derived context preview.
- **ResultPage**: vertical stack → 3-column dashboard (score / matrix / suggestions).

비즈니스 로직 (hooks, schemas, sessionContext, useSession, useSimulation 등)은 손대지 않았습니다.
