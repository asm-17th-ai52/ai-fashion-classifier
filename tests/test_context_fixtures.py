import json
from pathlib import Path

import pytest

from agents.recommendation import ContextResponse


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "context"


@pytest.mark.parametrize("path", sorted(FIXTURE_ROOT.glob("*.json")))
def test_context_fixture_is_schema_valid(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))

    context = ContextResponse.model_validate(payload)

    assert context.session_id
    assert context.dress_code.event_type
    assert context.dress_code.expected_formality_range[0] <= context.dress_code.expected_formality_range[1]
    assert context.dress_code.expected_categories.top
    assert context.dress_code.expected_categories.bottom
    assert context.dress_code.expected_categories.shoes
