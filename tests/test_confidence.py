"""tests/test_confidence.py

Testes de streamlit_app/confidence.py (US-2.3).
"""
from streamlit_app.confidence import attention_marker, confidence_badge_html, confidence_level


def test_alta_confidence_renders_green_badge():
    html = confidence_badge_html("alta")
    assert "#1e7e34" in html
    assert "ALTA" in html


def test_media_confidence_with_explanatory_text_renders_yellow_badge():
    html = confidence_badge_html("média - contém ambiguidades a validar via HITL")
    assert "#8a6d00" in html
    assert "MÉDIA" in html


def test_baixa_confidence_renders_red_badge():
    html = confidence_badge_html("baixa - poucos elementos detectados")
    assert "#a71d2a" in html


def test_unrecognized_text_renders_neutral_badge_with_raw_text():
    html = confidence_badge_html("não avaliado")
    assert "#555555" in html
    assert "não avaliado" in html


def test_confidence_level_recognizes_each_label():
    assert confidence_level("alta") == "alta"
    assert confidence_level("média - contém ambiguidades") == "média"
    assert confidence_level("baixa - poucos elementos") == "baixa"
    assert confidence_level("não avaliado") is None


def test_unrecognized_text_with_html_characters_is_escaped():
    html_result = confidence_badge_html("<script>alert(1)</script>")
    assert "<script>" not in html_result
    assert "&lt;script&gt;" in html_result


def test_attention_marker_with_note_returns_note_text():
    result = attention_marker(None, "rotulado 'AZ' no diagrama - ambíguo")
    assert result == "⚠️ rotulado 'AZ' no diagrama - ambíguo"


def test_attention_marker_with_low_confidence_and_no_note():
    assert attention_marker(0.3, None) == "⚠️ confiança baixa (30%)"


def test_attention_marker_with_high_confidence_and_no_note_returns_empty():
    assert attention_marker(0.9, None) == ""


def test_attention_marker_with_nothing_returns_empty():
    assert attention_marker(None, None) == ""


def test_attention_marker_note_takes_priority_over_low_confidence():
    assert attention_marker(0.2, "nota existente") == "⚠️ nota existente"
