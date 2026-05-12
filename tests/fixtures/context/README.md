# Context Agent Mock Fixtures

These fixtures are schema-valid `ContextResponse` payloads for replacing the
Context Agent during local development and integration tests.

| File | Scenario | Tier | Notes |
|---|---|---|---|
| `business_meeting.json` | Business meeting | `tier1` | Standard enum |
| `presentation.json` | Presentation | `tier1` | Standard enum |
| `wedding_guest.json` | Wedding guest | `tier1` | Standard enum |
| `office_daily.json` | Office daily | `tier1` | Standard enum |
| `casual_date.json` | Casual date | `tier1` | Standard enum |
| `school_daily.json` | School daily | `tier1` | Standard enum |
| `outdoor_activity.json` | Outdoor activity | `tier1` | Standard enum |
| `general.json` | General fallback | `fallback_general` | Offline fallback |
Existing interview fixtures are kept as-is because Recommendation golden tests
already depend on their exact contents.
