"""Testes unitários da interface de query do Knowledge Graph."""

from contextlib import nullcontext
from unittest.mock import MagicMock

import pytest

from knowledge.exceptions import ElementTypeNotFoundError
from knowledge.models import KGQueryResult, MitigationResult, ThreatResult
from knowledge.query import get_stride_threats


def _row(
    *,
    letter: str = "S",
    category: str = "Spoofing",
    threat_id: str = "threat-s-001",
) -> dict:
    return {
        "category_letter": letter,
        "category_name": category,
        "threat_id": threat_id,
        "threat_name": "Identity Spoofing",
        "threat_description": "An attacker impersonates a valid identity.",
        "threat_severity": "high",
        "mitigation_id": "mitigation-s-001",
        "mitigation_name": "Strong Authentication",
        "mitigation_description": "Require strong authentication controls.",
        "mitigation_control_type": "preventive",
    }


def _driver(*results):
    session = MagicMock()
    session.run.side_effect = results
    driver = MagicMock()
    driver.session.return_value = nullcontext(session)
    return driver, session


def test_returns_typed_taxonomy_result():
    exists = MagicMock()
    exists.single.return_value = {"element_type": "process"}
    driver, session = _driver(exists, [_row()])

    result = get_stride_threats("process", driver=driver)

    assert isinstance(result, KGQueryResult)
    assert isinstance(result.stride_results[0].threats[0], ThreatResult)
    assert isinstance(result.stride_results[0].mitigations[0], MitigationResult)
    assert result.total_threats == 1
    assert result.query_source == "taxonomy"
    assert session.run.call_count == 2


def test_combines_enrichment_and_normalizes_service_alias():
    exists = MagicMock()
    exists.single.return_value = {"element_type": "data_store"}
    taxonomy_row = _row(letter="I", category="InformationDisclosure")
    enriched_row = _row(letter="I", category="InformationDisclosure")
    driver, session = _driver(exists, [taxonomy_row], [enriched_row])

    result = get_stride_threats(
        "data_store",
        cloud_service="Amazon S3",
        driver=driver,
    )

    assert result.cloud_service == "S3"
    assert result.query_source == "both"
    assert result.total_threats == 1
    assert len(result.stride_results[0].mitigations) == 1
    assert session.run.call_args_list[2].kwargs["cloud_service"] == "S3"
    assert "COVERS_SERVICE" in session.run.call_args_list[2].args[0]
    assert "COVERS_CATEGORY" in session.run.call_args_list[2].args[0]


def test_uses_stride_canonical_order():
    exists = MagicMock()
    exists.single.return_value = {"element_type": "process"}
    rows = [
        _row(letter="D", category="DenialOfService", threat_id="threat-d-001"),
        _row(letter="S", category="Spoofing", threat_id="threat-s-001"),
        _row(letter="T", category="Tampering", threat_id="threat-t-001"),
    ]
    driver, _ = _driver(exists, rows)

    result = get_stride_threats("process", driver=driver)

    assert [item.letter for item in result.stride_results] == ["S", "T", "D"]


def test_raises_for_unknown_element_type():
    missing = MagicMock()
    missing.single.return_value = None
    driver, session = _driver(missing)

    with pytest.raises(ElementTypeNotFoundError) as exc_info:
        get_stride_threats("queue", driver=driver)

    assert exc_info.value.element_type == "queue"
    assert session.run.call_count == 1
