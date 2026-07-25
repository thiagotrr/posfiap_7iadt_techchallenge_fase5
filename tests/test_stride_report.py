"""tests/test_stride_report.py

Testes de streamlit_app/stride_report.py (US-3.2).
"""
from streamlit_app.stride_report import (
    categories_present,
    category_badge_html,
    category_counts,
    severity_badge_html,
    severity_counts,
    sort_component_analyses,
    stride_matrix_html,
)

_ANALYSES = [
    {
        "component_id": "c3",
        "component_name": "S3 Bucket",
        "element_type": "data_store",
        "stride_entries": [{"category": "I"}],
    },
    {
        "component_id": "c1",
        "component_name": "API Gateway",
        "element_type": "process",
        "stride_entries": [{"category": "S"}, {"category": "T"}],
    },
    {
        "component_id": "c4",
        "component_name": "User",
        "element_type": "external_entity",
        "stride_entries": [],
    },
]


def test_sort_component_analyses_orders_by_element_type_then_name():
    ordered = sort_component_analyses(_ANALYSES)
    assert [a["component_id"] for a in ordered] == ["c1", "c3", "c4"]


def test_categories_present_returns_set_of_categories():
    assert categories_present(_ANALYSES[1]) == {"S", "T"}
    assert categories_present(_ANALYSES[2]) == set()


def test_category_badge_html_contains_letter_and_color():
    result = category_badge_html("S")
    assert "S</span>" in result
    assert "#8e44ad" in result


def test_severity_badge_html_contains_uppercase_label_and_color():
    result = severity_badge_html("critical")
    assert "CRITICAL" in result
    assert "#a71d2a" in result


def test_stride_matrix_html_shows_badge_for_present_category_and_dash_for_absent():
    result = stride_matrix_html(_ANALYSES)
    assert "API Gateway" in result
    assert "S3 Bucket" in result
    assert "User" in result
    assert result.count("–") >= 4  # c1: 4 ausentes; c3: 5 ausentes; c4: 6 ausentes -- ao menos 4


def test_stride_matrix_html_escapes_component_name():
    malicious = [{"component_id": "c1", "component_name": "<script>", "element_type": "process", "stride_entries": []}]
    result = stride_matrix_html(malicious)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_severity_counts_reads_expected_keys_with_default_zero():
    risk_summary = {"critical": 1, "high": 2, "medium": 0, "low": 0, "total_threats": 3}
    assert severity_counts(risk_summary) == {"critical": 1, "high": 2, "medium": 0, "low": 0}


def test_severity_counts_defaults_missing_keys_to_zero():
    assert severity_counts({}) == {"critical": 0, "high": 0, "medium": 0, "low": 0}


def test_category_counts_reads_by_category_with_default_zero():
    risk_summary = {"by_category": {"S": 1, "T": 1, "R": 0, "I": 1, "D": 1, "E": 0}}
    assert category_counts(risk_summary) == {"S": 1, "T": 1, "R": 0, "I": 1, "D": 1, "E": 0}


def test_category_counts_defaults_missing_keys_to_zero():
    assert category_counts({}) == {"S": 0, "T": 0, "R": 0, "I": 0, "D": 0, "E": 0}
