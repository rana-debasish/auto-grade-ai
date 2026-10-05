import pytest

from services.evaluation_manager import _normalize_result


@pytest.mark.parametrize('payload', [
    {'questions': [{'q_no': 1, 'marks': 6, 'feedback': 'too high'}]},
    {'questions': [{'q_no': 1, 'marks': 'not a number'}]},
    {'questions': []},
])
def test_invalid_ai_marks_or_missing_questions_are_rejected(payload):
    with pytest.raises(ValueError):
        _normalize_result(payload, [{'q_no': 1, 'max_marks': 5}])


def test_gemini_call_parses_structured_json(monkeypatch):
    import services.gemini_service as gemini

    class Response:
        text = '{"ok": true}'
        usage_metadata = None

    class Model:
        def __init__(self, _name): pass
        def generate_content(self, *_args, **_kwargs): return Response()

    monkeypatch.setattr(gemini, 'API_KEY', 'test-key')
    monkeypatch.setattr(gemini.genai, 'GenerativeModel', Model)
    assert gemini.call_gemini('prompt') == {'ok': True}
